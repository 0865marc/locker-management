"""Sequential PostgreSQL invariants; concurrency is checked separately."""
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from uuid import uuid4
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from tests.integration.support import PostgresTestCase
from sqlmodel import select
from adapters.database.sqlmodel_lockers import SqlModelLockerRepository, AssignmentRow, CompartmentRow
from adapters.database.sqlmodel_repositories import SqlModelDeliveryRepository, SqlModelReturnRepository
from domain.lockers import Dimensions, CompartmentBatch, CapacityConflictError, LockerNotFoundError
from domain.models import Delivery, Return

D = Dimensions(10, 20, 30)
NOW = datetime(2026, 10, 15, tzinfo=timezone.utc)

class LockerRepositoryTests(PostgresTestCase):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.lockers = SqlModelLockerRepository(self.sessions)
        self.deliveries = SqlModelDeliveryRepository(self.sessions)
        self.returns = SqlModelReturnRepository(self.sessions)

    async def create(self, quantity=1, active=True, location='Site'):
        return await self.lockers.create(location, [CompartmentBatch(quantity, D)], active)

    def parcel(self, flow='delivery'):
        return Delivery('T', 'C', 'Ana', NOW) if flow == 'delivery' else Return('T', 'C', NOW)

    async def test_batches_configuration_growth_identity_and_retirement(self):
        with self.assertRaises(ValueError):
            await self.create(1001)
        self.assertEqual(await self.lockers.list_all(), [])
        locker = await self.create(1000)
        old_ids = {c.id for c in locker.compartments}
        grown = await self.lockers.add_compartments(locker.id, [CompartmentBatch(2, D)])
        self.assertEqual(grown.compartment_count, 1002)
        self.assertTrue(old_ids <= {c.id for c in grown.compartments})
        with self.assertRaises(ValueError):
            await self.lockers.add_compartments(locker.id, [CompartmentBatch(501, D), CompartmentBatch(500, D)])
        cell = locker.compartments[0]
        resized = await self.lockers.update_compartment(locker.id, cell.id, Dimensions(1, 2, 3), False)
        self.assertEqual(resized.id, cell.id)
        self.assertFalse(resized.enabled)
        await self.lockers.retire_compartment(locker.id, cell.id)
        self.assertEqual((await self.lockers.get_by_id(locker.id)).compartment_count, 1001)
        async with self.sessions() as session:
            self.assertTrue((await session.get(CompartmentRow, cell.id)).retired)
        with self.assertRaises(LockerNotFoundError):
            await self.lockers.update_compartment(locker.id, cell.id, enabled=True)
        other = await self.create()
        with self.assertRaises(LockerNotFoundError):
            await self.lockers.retire_compartment(other.id, grown.compartments[1].id)

    async def test_shared_capacity_failure_reasons_and_snapshot_is_read_only(self):
        self.assertEqual((await self.lockers.availability('Site', D)).reason, 'NO_LOCKER')
        inactive = await self.create(active=False)
        self.assertEqual((await self.lockers.availability('Site', D)).reason, 'LOCKER_INACTIVE')
        locker = await self.create()
        self.assertEqual((await self.lockers.availability('Site', Dimensions(100, 100, 100))).reason, 'NO_COMPATIBLE_CELL')
        received = await self.deliveries.receive_in_locker(self.parcel(), locker.id, D)
        incompatible = await self.lockers.create('Site', [CompartmentBatch(1, Dimensions(1, 1, 1))])
        snapshot = await self.lockers.availability('Site', D)
        self.assertEqual(snapshot.reason, 'FULL')
        outcomes = {result.locker_id: result for result in snapshot.lockers}
        self.assertEqual(set(outcomes), {inactive.id, locker.id, incompatible.id})
        self.assertEqual((outcomes[locker.id].reason, outcomes[locker.id].compatible_count, outcomes[locker.id].available_count), ('FULL', 1, 0))
        self.assertEqual((outcomes[incompatible.id].reason, outcomes[incompatible.id].compatible_count, outcomes[incompatible.id].available_count), ('NO_COMPATIBLE_CELL', 0, 0))
        self.assertEqual((outcomes[inactive.id].reason, outcomes[inactive.id].compatible_count, outcomes[inactive.id].available_count), ('LOCKER_INACTIVE', 1, 0))
        for identifier, dims, reason in ((inactive.id,D,'LOCKER_INACTIVE'), (locker.id,Dimensions(100,100,100),'NO_COMPATIBLE_CELL'), (locker.id,D,'FULL')):
            with self.assertRaises(CapacityConflictError) as error:
                await self.returns.receive_in_locker(self.parcel('return'), identifier, dims)
            self.assertEqual(error.exception.code, reason)
        with self.assertRaises(LockerNotFoundError):
            await self.returns.receive_in_locker(self.parcel('return'), uuid4(), D)
        self.assertEqual(await self.returns.list_all(), [])
        self.assertEqual(await self.deliveries.list_all(), [received])
        mixed = await self.create(4)
        occupied = await self.returns.receive_in_locker(self.parcel('return'), mixed.id, D)
        free_cells = [cell for cell in mixed.compartments if cell.id != occupied.compartment_id]
        await self.lockers.update_compartment(mixed.id, free_cells[0].id, enabled=False)
        await self.lockers.retire_compartment(mixed.id, free_cells[1].id)
        # All four cells physically fit, but disabled/retired cells do not contribute.
        snapshot = await self.lockers.availability('Site', D)
        self.assertEqual(snapshot.reason, 'AVAILABLE')
        outcomes = {result.locker_id: result for result in snapshot.lockers}
        self.assertEqual(set(outcomes), {inactive.id, locker.id, incompatible.id, mixed.id})
        self.assertEqual((outcomes[mixed.id].reason, outcomes[mixed.id].compatible_count, outcomes[mixed.id].available_count), ('AVAILABLE', 2, 1))
        self.assertEqual((outcomes[locker.id].reason, outcomes[locker.id].compatible_count, outcomes[locker.id].available_count), ('FULL', 1, 0))
        self.assertEqual(outcomes[incompatible.id].reason, 'NO_COMPATIBLE_CELL')
        self.assertEqual(outcomes[inactive.id].reason, 'LOCKER_INACTIVE')
        configuration = await self.lockers.get_by_id(mixed.id)
        self.assertEqual(configuration.compartment_count, 3)
        self.assertEqual(sum(cell.occupied for cell in configuration.compartments), 1)
        self.assertEqual(sum(not cell.enabled for cell in configuration.compartments), 1)

        self.assertEqual(await self.lockers.list_all('site'), [])
        case_distinct = await self.create(location='site')
        prefix_distinct = await self.create(location='Site annex')
        exact_ids = {inactive.id, locker.id, incompatible.id, mixed.id}
        filtered = await self.lockers.list_all('Site')
        self.assertEqual([item.id for item in filtered], sorted(exact_ids))
        self.assertEqual([item.id for item in await self.lockers.list_all('site')], [case_distinct.id])
        self.assertEqual([item.id for item in await self.lockers.list_all('Site annex')], [prefix_distinct.id])
        self.assertEqual({result.locker_id for result in (await self.lockers.availability(' Site ', D)).lockers}, exact_ids)
        self.assertEqual((await self.lockers.availability('SITE', D)).reason, 'NO_LOCKER')

    async def test_all_exits_history_inactive_and_old_exit_cannot_release_new_occupant(self):
        for flow, transition in (('delivery','collect'), ('delivery','return_to_carrier'), ('return','hand_over')):
            locker = await self.create()
            repo = self.deliveries if flow == 'delivery' else self.returns
            original = self.parcel(flow)
            received = await repo.receive_in_locker(original, locker.id, Dimensions(30,10,20))
            self.assertEqual(received.parcel_dimensions, Dimensions(30,10,20))
            self.assertIsNone(original.locker_id)
            for operation in (lambda: self.lockers.update_compartment(locker.id, received.compartment_id, enabled=False), lambda: self.lockers.update_compartment(locker.id, received.compartment_id, dimensions=Dimensions(1,1,1)), lambda: self.lockers.retire_compartment(locker.id, received.compartment_id)):
                with self.assertRaises(CapacityConflictError):
                    await operation()
            await self.lockers.set_active(locker.id, False)
            terminal = getattr(received, transition)(NOW + timedelta(seconds=1))
            self.assertTrue(await repo.save_exit(terminal))
            await self.lockers.set_active(locker.id, True)
            second = await self.returns.receive_in_locker(self.parcel('return'), locker.id, D)
            self.assertFalse(await repo.save_exit(terminal))
            self.assertTrue((await self.lockers.get_by_id(locker.id)).compartments[0].occupied)
            self.assertTrue(await self.returns.save_exit(second.hand_over(NOW + timedelta(seconds=2))))
            await self.lockers.update_compartment(locker.id, received.compartment_id, Dimensions(1,1,1))
            await self.lockers.retire_compartment(locker.id, received.compartment_id)
            self.assertEqual(await repo.get_by_id(received.id), terminal)
            with self.assertRaises(ValueError):
                await repo.save(received)

    async def test_before_commit_failure_rolls_back_both_halves(self):
        locker = await self.create()
        def fail(session):
            raise RuntimeError('before commit')
        for repo, flow, transition in ((self.deliveries,'delivery','collect'), (self.returns,'return','hand_over')):
            original = self.parcel(flow)
            event.listen(Session, 'before_commit', fail)
            try:
                with self.assertRaisesRegex(RuntimeError, 'before commit'):
                    await repo.receive_in_locker(original, locker.id, D)
            finally:
                event.remove(Session, 'before_commit', fail)
            self.assertIsNone(await repo.get_by_id(original.id))
            self.assertFalse((await self.lockers.get_by_id(locker.id)).compartments[0].occupied)
            received = await repo.receive_in_locker(original, locker.id, D)
            terminal = getattr(received, transition)(NOW + timedelta(seconds=1))
            event.listen(Session, 'before_commit', fail)
            try:
                with self.assertRaisesRegex(RuntimeError, 'before commit'):
                    await repo.save_exit(terminal)
            finally:
                event.remove(Session, 'before_commit', fail)
            self.assertEqual(await repo.get_by_id(original.id), received)
            self.assertTrue((await self.lockers.get_by_id(locker.id)).compartments[0].occupied)
            self.assertTrue(await repo.save_exit(terminal))

    async def test_assignment_constraints_foreign_keys_and_unique_history(self):
        locker = await self.create(2)
        parcel = self.parcel()
        await self.deliveries.save(parcel)
        other = self.parcel('return')
        await self.returns.save(other)
        values = dict(compartment_id=locker.compartments[0].id, delivery_id=parcel.id,
                      width_mm=1, height_mm=2, depth_mm=3, assigned_at=NOW)
        async with self.sessions.begin() as session:
            session.add(AssignmentRow(id=uuid4(), **values))
        invalid = [values, values | {'delivery_id':None}, values | {'return_id':other.id}, values | {'delivery_id':uuid4()}, values | {'compartment_id':uuid4()}, values | {'width_mm':0}, values | {'released_at':NOW-timedelta(seconds=1)}, values | {'delivery_id':None,'return_id':other.id}]
        for item in invalid:
            with self.subTest(item=item), self.assertRaises(IntegrityError):
                async with self.sessions.begin() as session:
                    session.add(AssignmentRow(id=uuid4(), **item))
        async with self.sessions.begin() as session:
            rows = (await session.exec(select(AssignmentRow))).all()
            self.assertEqual(len(rows),1)
            rows[0].released_at = NOW
        with self.assertRaises(IntegrityError):
            async with self.sessions.begin() as session:
                session.add(AssignmentRow(id=uuid4(), **(values | {'compartment_id':locker.compartments[1].id})))
        async with self.sessions.begin() as session:
            session.add(AssignmentRow(id=uuid4(), **(values | {'delivery_id':None,'return_id':other.id})))

    async def test_configuration_failures_are_atomic_and_snapshots_do_not_write(self):
        def fail(session):
            raise RuntimeError('configuration commit failed')
        event.listen(Session, 'before_commit', fail)
        try:
            with self.assertRaises(RuntimeError):
                await self.create(2)
        finally:
            event.remove(Session, 'before_commit', fail)
        self.assertEqual(await self.lockers.list_all(), [])
        locker = await self.create()
        event.listen(Session, 'before_commit', fail)
        try:
            with self.assertRaises(RuntimeError):
                await self.lockers.add_compartments(locker.id,[CompartmentBatch(2,D)])
        finally:
            event.remove(Session, 'before_commit', fail)
        self.assertEqual(await self.lockers.get_by_id(locker.id), locker)
        statements = []
        def capture(connection,cursor,statement,parameters,context,executemany):
            statements.append(statement)
        event.listen(self.engine.sync_engine, 'before_cursor_execute', capture)
        try:
            for _ in range(2):
                self.assertEqual((await self.lockers.availability('Site',D)).reason,'AVAILABLE')
        finally:
            event.remove(self.engine.sync_engine, 'before_cursor_execute', capture)
        self.assertEqual(len(statements),2)
        self.assertTrue(all(s.lstrip().upper().startswith('SELECT') for s in statements))

    async def test_geography_round_trip_atomic_replacement_clearing_and_legacy_alias(self) -> None:
        from domain.lockers import Address, Coordinates, LockerPatch
        address = Address('ES', '01001', ' Araba ', ' Vitoria ', ' Calle ', ' 12B ')
        coordinates = Coordinates(-90, 180)
        locker = await self.lockers.create(None, [CompartmentBatch(1, D)], address=address, coordinates=coordinates)
        fresh = SqlModelLockerRepository(self.sessions)
        self.assertEqual(await fresh.get_by_id(locker.id), locker)
        self.assertIsNone(locker.location_id)
        self.assertIn(locker, await fresh.list_all())
        self.assertEqual(await fresh.list_all('01001'), [])
        self.assertEqual((await fresh.availability('01001', D)).reason, 'NO_LOCKER')
        received = await self.deliveries.receive_in_locker(self.parcel(), locker.id, D)
        replacement = Address('ES', '28001', 'Madrid', 'Madrid', 'Otra', 's/n')
        patched = await fresh.update(locker.id, LockerPatch(address=replacement, coordinates=Coordinates(90, -180), address_supplied=True, coordinates_supplied=True))
        self.assertEqual(patched.address, replacement)
        self.assertEqual(patched.coordinates, Coordinates(90, -180))
        self.assertEqual(patched.compartments[0].id, received.compartment_id)
        self.assertTrue(patched.compartments[0].occupied)
        inactive = await fresh.set_active(locker.id, False)
        self.assertEqual((inactive.address, inactive.coordinates), (replacement, Coordinates(90, -180)))
        cleared = await fresh.update(locker.id, LockerPatch(address_supplied=True))
        self.assertIsNone(cleared.address)
        self.assertEqual(cleared.coordinates, Coordinates(90, -180))
        cleared = await fresh.update(locker.id, LockerPatch(coordinates_supplied=True))
        self.assertEqual((cleared.location_id, cleared.address, cleared.coordinates), (None, None, None))
        self.assertEqual(await fresh.get_by_id(locker.id), cleared)
        self.assertTrue(await self.deliveries.save_exit(received.collect(NOW + timedelta(seconds=1))))
        legacy = await self.create()
        self.assertEqual((legacy.location_id, legacy.address, legacy.coordinates), ('Site', None, None))
        self.assertEqual([item.id for item in await fresh.list_all('Site')], [legacy.id])

    async def test_geography_replacement_failure_rolls_back_active_address_and_coordinates(self) -> None:
        from domain.lockers import Address, Coordinates, LockerPatch
        locker = await self.create()
        def fail(session: Session) -> None:
            raise RuntimeError('geography commit failed')
        event.listen(Session, 'before_commit', fail)
        try:
            with self.assertRaisesRegex(RuntimeError, 'geography commit'):
                await self.lockers.update(locker.id, LockerPatch(active=False,
                    address=Address('ES', '01001', 'P', 'C', 'S', 'N'), address_supplied=True,
                    coordinates=Coordinates(1, 2), coordinates_supplied=True))
        finally:
            event.remove(Session, 'before_commit', fail)
        self.assertEqual(await self.lockers.get_by_id(locker.id), locker)
