"""Production adapters running against the official local workerd D1 binding.

The caller is CPython; these are native D1 semantics, not Python Workers proof.
"""

import asyncio
import json
import unittest
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from native_d1 import NativeD1

from adapters.database.d1 import (
    D1DeliveryRepository,
    D1LockerRepository,
    D1ReturnRepository,
)
from adapters.database.d1.bindings import (
    D1BindingError,
    D1Database,
    D1PreparedStatement,
)
from adapters.database.d1.core import query, result, text
from application.persistence import PersistenceError
from domain.deliveries import Delivery
from domain.lockers import (
    CapacityConflictError,
    CompartmentBatch,
    Dimensions,
    LockerNotFoundError,
    LockerPatch,
    select_compartment,
)
from domain.returns import Return

NOW = datetime(2026, 1, 2, 3, 4, 5, 123456, tzinfo=timezone.utc)
DIMS = Dimensions(10, 20, 30)


class ControlledDatabase:
    def __init__(self, database: D1Database, mode: str) -> None:
        self.database = database
        self.mode = mode
        self.calls = 0
        self.ready = asyncio.Event()
        self.resume = asyncio.Event()

    def prepare(self, sql: str) -> D1PreparedStatement:
        return self.database.prepare(sql)

    async def batch(self, statements: Sequence[D1PreparedStatement]) -> object:
        self.calls += 1
        if self.mode == "lose":
            # A conclusive zero-change CAS, with all real business statements retained.
            replacement = self.prepare("UPDATE lockers SET revision=revision+1 WHERE 0")
            return await self.database.batch([replacement, *statements[1:]])
        if self.mode == "barrier" and self.calls == 1:
            self.ready.set()
            await self.resume.wait()
        if self.mode == "rollback":
            return await self.database.batch(
                [
                    *statements[:2],
                    self.prepare(
                        "INSERT INTO locker_compartments(id) VALUES ('invalid')"
                    ),
                    *statements[2:],
                ]
            )
        result = await self.database.batch(statements)
        if self.mode == "unknown":
            raise D1BindingError("transport failed after server commit")
        return result


class RepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.database = await NativeD1().__aenter__()
        self.addAsyncCleanup(self.database.close)
        await self.database.migrate()
        self.lockers = D1LockerRepository(lambda: self.database)
        self.deliveries = D1DeliveryRepository(lambda: self.database)
        self.returns = D1ReturnRepository(lambda: self.database)

    async def locker(self, count: int = 1):
        return await self.lockers.create("location", [CompartmentBatch(count, DIMS)])

    def delivery(self) -> Delivery:
        return Delivery("tracking", "carrier", "recipient", NOW)

    def parcel_return(self) -> Return:
        return Return("return", "carrier", NOW)

    async def test_unassigned_roundtrip_and_single_exits(self) -> None:
        delivery = self.delivery()
        parcel_return = self.parcel_return()
        await self.deliveries.save(delivery)
        await self.returns.save(parcel_return)
        self.assertEqual(await self.deliveries.get_by_id(delivery.id), delivery)
        self.assertEqual(await self.returns.get_by_id(parcel_return.id), parcel_return)
        self.assertTrue(await self.deliveries.save_exit(delivery.collect(NOW)))
        self.assertFalse(
            await self.deliveries.save_exit(delivery.return_to_carrier(NOW))
        )
        self.assertTrue(await self.returns.save_exit(parcel_return.hand_over(NOW)))
        self.assertFalse(await self.returns.save_exit(parcel_return.hand_over(NOW)))

    async def test_bulk_maxima_and_full_coherent_reads(self) -> None:
        self.database.statements.clear()
        locker = await self.locker(1000)
        self.assertEqual(len(locker.compartments), 1000)
        self.assertEqual(len(self.database.statements), 3)
        with self.assertRaises(ValueError):
            await self.locker(1001)
        self.database.statements.clear()
        locker = await self.lockers.add_compartments(
            locker.id, [CompartmentBatch(1000, DIMS)]
        )
        self.assertEqual(len(locker.compartments), 2000)
        self.assertEqual(len(self.database.statements), 4)
        self.assertTrue(
            all(len(params) <= 100 for _, params in self.database.statements)
        )
        self.database.statements.clear()
        found = await self.lockers.get_by_id(locker.id)
        self.assertIsNotNone(found)
        assert found is not None
        self.assertEqual(len(found.compartments), 2000)
        self.assertEqual(len(self.database.statements), 1)

    async def receive(
        self, kind: str, locker_id: UUID, dimensions: Dimensions
    ) -> Delivery | Return:
        if kind == "delivery":
            return await self.deliveries.receive_in_locker(
                self.delivery(), locker_id, dimensions
            )
        return await self.returns.receive_in_locker(
            self.parcel_return(), locker_id, dimensions
        )

    def assert_compact_reception(self) -> None:
        self.assertEqual(len(self.database.statements), 4)
        self.assertEqual(len(self.database.results), 2)
        decisions = result(self.database.results[0]).results
        self.assertEqual(len(decisions), 1)
        # Only the decision crosses the binding: never cell dimensions or volume limbs.
        self.assertEqual(
            set(decisions[0]),
            {"id", "active", "revision", "has_compatible", "candidate_id"},
        )
        self.assertLess(len(json.dumps(decisions[0])), 256)
        self.assertTrue(
            all(len(params) <= 100 for _, params in self.database.statements)
        )

    async def test_both_receptions_transfer_one_decision_for_2000_cells(self) -> None:
        locker = await self.locker(1000)
        locker = await self.lockers.add_compartments(
            locker.id, [CompartmentBatch(1000, Dimensions(30, 10, 20))]
        )
        # A rotated parcel fits equal-volume cells; UUID breaks their tie.
        dimensions = Dimensions(20, 30, 10)
        for kind in ("delivery", "return"):
            with self.subTest(kind=kind):
                current = await self.lockers.get_by_id(locker.id)
                assert current is not None
                self.assertEqual(len(current.compartments), 2000)
                expected = select_compartment(current.compartments, dimensions)
                assert expected is not None
                self.database.statements.clear()
                self.database.results.clear()
                parcel = await self.receive(kind, locker.id, dimensions)
                self.assert_compact_reception()
                self.assertEqual(parcel.compartment_id, expected.id)
                self.assertEqual(parcel.parcel_dimensions, dimensions)
                found = await self.lockers.get_by_id(locker.id)
                assert found is not None
                self.assertEqual(len(found.compartments), 2000)
                self.assertEqual(
                    sum(cell.occupied for cell in found.compartments),
                    1 if kind == "delivery" else 2,
                )

    async def test_compact_decisions_preserve_error_precedence_for_both_flows(
        self,
    ) -> None:
        for kind in ("delivery", "return"):
            with self.subTest(kind=kind):
                self.database.statements.clear()
                self.database.results.clear()
                with self.assertRaises(LockerNotFoundError):
                    await self.receive(kind, uuid4(), DIMS)
                self.assertEqual(len(self.database.statements), 1)
                self.assertEqual(result(self.database.results[0]).results, ())
                locker = await self.lockers.create(
                    "errors",
                    [
                        CompartmentBatch(1, DIMS, enabled=False),
                        CompartmentBatch(1, Dimensions(1, 1, 1)),
                        CompartmentBatch(1, Dimensions(30, 20, 10)),
                    ],
                )
                retired = next(
                    cell
                    for cell in locker.compartments
                    if cell.dimensions == Dimensions(30, 20, 10)
                )
                await self.lockers.retire_compartment(locker.id, retired.id)
                await self.lockers.set_active(locker.id, False)
                for code in ("LOCKER_INACTIVE", "NO_COMPATIBLE_CELL", "FULL"):
                    self.database.statements.clear()
                    self.database.results.clear()
                    with self.assertRaises(CapacityConflictError) as failure:
                        await self.receive(kind, locker.id, DIMS)
                    self.assertEqual(failure.exception.code, code)
                    self.assertEqual(len(self.database.statements), 1)
                    decisions = result(self.database.results[0]).results
                    self.assertEqual(len(decisions), 1)
                    self.assertLess(len(json.dumps(decisions[0])), 256)
                    if code == "LOCKER_INACTIVE":
                        await self.lockers.set_active(locker.id, True)
                    elif code == "NO_COMPATIBLE_CELL":
                        cell = next(
                            c for c in locker.compartments if c.dimensions == DIMS
                        )
                        await self.lockers.update_compartment(
                            locker.id, cell.id, enabled=True
                        )
                        # Active occupancy of either custody type makes the candidate FULL.
                        await self.receive(
                            "return" if kind == "delivery" else "delivery",
                            locker.id,
                            DIMS,
                        )
                parcels = await (
                    self.deliveries.list_all()
                    if kind == "delivery"
                    else self.returns.list_all()
                )
                self.assertTrue(
                    all(parcel.locker_id != locker.id for parcel in parcels)
                )

    async def test_last_cell_race_rechecks_after_cas(self) -> None:
        locker = await self.locker()
        controlled = ControlledDatabase(self.database, "barrier")
        loser = D1DeliveryRepository(lambda: controlled)
        task = asyncio.create_task(
            loser.receive_in_locker(self.delivery(), locker.id, DIMS)
        )
        await asyncio.wait_for(controlled.ready.wait(), 5)
        winner = await self.returns.receive_in_locker(
            self.parcel_return(), locker.id, DIMS
        )
        controlled.resume.set()
        with self.assertRaises(CapacityConflictError) as failure:
            await task
        self.assertEqual(failure.exception.code, "FULL")
        self.assertEqual(await self.deliveries.list_all(), [])
        self.assertEqual(await self.returns.list_all(), [winner])

    async def test_configuration_wins_stale_reception(self) -> None:
        locker = await self.locker()
        controlled = ControlledDatabase(self.database, "barrier")
        task = asyncio.create_task(
            D1DeliveryRepository(lambda: controlled).receive_in_locker(
                self.delivery(), locker.id, DIMS
            )
        )
        await asyncio.wait_for(controlled.ready.wait(), 5)
        await self.lockers.update_compartment(
            locker.id, locker.compartments[0].id, enabled=False
        )
        controlled.resume.set()
        with self.assertRaises(CapacityConflictError) as failure:
            await task
        self.assertEqual(failure.exception.code, "NO_COMPATIBLE_CELL")
        self.assertEqual(await self.deliveries.list_all(), [])

    async def test_rollback_reverts_parcel_assignment_revision_and_token(self) -> None:
        locker = await self.locker()
        before = await query(
            self.database,
            "SELECT revision,mutation_token FROM lockers WHERE id=?",
            str(locker.id),
        )
        controlled = ControlledDatabase(self.database, "rollback")
        with self.assertRaises(PersistenceError):
            await D1DeliveryRepository(lambda: controlled).receive_in_locker(
                self.delivery(), locker.id, DIMS
            )
        self.assertEqual(
            await query(
                self.database,
                "SELECT revision,mutation_token FROM lockers WHERE id=?",
                str(locker.id),
            ),
            before,
        )
        self.assertEqual(await self.deliveries.list_all(), [])
        self.assertEqual(
            await query(self.database, "SELECT id FROM locker_assignments"), ()
        )
        await self.deliveries.receive_in_locker(self.delivery(), locker.id, DIMS)

    async def test_every_existing_locker_writer_cas_zero_changes(self) -> None:
        locker = await self.locker(3)
        occupied = await self.deliveries.receive_in_locker(
            self.delivery(), locker.id, DIMS
        )
        returned = await self.returns.receive_in_locker(
            self.parcel_return(), locker.id, DIMS
        )
        await self.deliveries.save_exit(occupied.collect(NOW))
        pending = await self.deliveries.receive_in_locker(
            self.delivery(), locker.id, DIMS
        )
        configuration = await self.lockers.get_by_id(locker.id)
        assert configuration is not None
        free_id = next(c.id for c in configuration.compartments if not c.occupied)
        controlled = ControlledDatabase(self.database, "lose")
        lockers = D1LockerRepository(lambda: controlled)
        deliveries = D1DeliveryRepository(lambda: controlled)
        returns = D1ReturnRepository(lambda: controlled)
        operations = [
            lambda: lockers.set_active(locker.id, False),
            lambda: lockers.update(locker.id, LockerPatch(coordinates_supplied=True)),
            lambda: lockers.add_compartments(locker.id, [CompartmentBatch(1, DIMS)]),
            lambda: lockers.update_compartment(locker.id, free_id, Dimensions(2, 3, 4)),
            lambda: lockers.retire_compartment(locker.id, free_id),
            lambda: deliveries.receive_in_locker(self.delivery(), locker.id, DIMS),
            lambda: returns.receive_in_locker(self.parcel_return(), locker.id, DIMS),
            lambda: returns.save_exit(returned.hand_over(NOW)),
            lambda: deliveries.save_exit(pending.collect(NOW)),
            lambda: deliveries.save_exit(pending.return_to_carrier(NOW)),
        ]
        before = await query(
            self.database,
            "SELECT revision,mutation_token FROM lockers WHERE id=?",
            str(locker.id),
        )
        for index, operation in enumerate(operations):
            controlled.calls = 0
            self.database.statements.clear()
            with self.assertRaises(PersistenceError):
                await operation()
            self.assertEqual(controlled.calls, 3)
            if index in (
                5,
                6,
            ):  # Delivery and return receptions: four statements per attempt.
                self.assertEqual(len(self.database.statements), 12)
            else:
                self.assertLessEqual(len(self.database.statements), 24)
            self.assertTrue(
                all(len(params) <= 100 for _, params in self.database.statements)
            )
            self.assertEqual(
                await query(
                    self.database,
                    "SELECT revision,mutation_token FROM lockers WHERE id=?",
                    str(locker.id),
                ),
                before,
            )
        self.assertEqual(len(await self.deliveries.list_all()), 2)
        self.assertEqual(len(await self.returns.list_all()), 1)

    async def test_reception_wins_stale_configuration(self) -> None:
        for change in ("resize", "disable", "retire"):
            locker = await self.locker()
            controlled = ControlledDatabase(self.database, "barrier")
            lockers = D1LockerRepository(lambda: controlled)
            cell_id = locker.compartments[0].id
            if change == "retire":
                operation = lockers.retire_compartment(locker.id, cell_id)
            else:
                operation = lockers.update_compartment(
                    locker.id,
                    cell_id,
                    dimensions=Dimensions(1, 1, 1) if change == "resize" else None,
                    enabled=False if change == "disable" else None,
                )
            task = asyncio.create_task(operation)
            await asyncio.wait_for(controlled.ready.wait(), 5)
            parcel = await self.deliveries.receive_in_locker(
                self.delivery(), locker.id, DIMS
            )
            controlled.resume.set()
            with self.assertRaises(CapacityConflictError) as failure:
                await task
            self.assertEqual(failure.exception.code, "CELL_OCCUPIED")
            self.assertEqual(await self.deliveries.get_by_id(parcel.id), parcel)

    async def test_rolled_back_contender_does_not_cause_full(self) -> None:
        locker = await self.locker()
        paused = ControlledDatabase(self.database, "barrier")
        parcel = self.delivery()
        task = asyncio.create_task(
            D1DeliveryRepository(lambda: paused).receive_in_locker(
                parcel, locker.id, DIMS
            )
        )
        await asyncio.wait_for(paused.ready.wait(), 5)
        broken = ControlledDatabase(self.database, "rollback")
        with self.assertRaises(PersistenceError):
            await D1ReturnRepository(lambda: broken).receive_in_locker(
                self.parcel_return(), locker.id, DIMS
            )
        paused.resume.set()
        result = await task
        self.assertEqual(result.id, parcel.id)
        self.assertEqual(await self.returns.list_all(), [])
        self.assertEqual(
            len(
                await query(
                    self.database,
                    "SELECT id FROM locker_assignments WHERE released_at IS NULL",
                )
            ),
            1,
        )

    async def test_exit_history_reoccupation_and_unknown_commit(self) -> None:
        locker = await self.locker()
        original = await self.deliveries.receive_in_locker(
            self.delivery(), locker.id, DIMS
        )
        controlled = ControlledDatabase(self.database, "barrier")
        task = asyncio.create_task(
            D1DeliveryRepository(lambda: controlled).save_exit(original.collect(NOW))
        )
        await asyncio.wait_for(controlled.ready.wait(), 5)
        self.assertTrue(
            await self.deliveries.save_exit(original.return_to_carrier(NOW))
        )
        new = await self.returns.receive_in_locker(
            self.parcel_return(), locker.id, DIMS
        )
        controlled.resume.set()
        self.assertFalse(await task)
        rows = await query(
            self.database,
            "SELECT return_id FROM locker_assignments WHERE released_at IS NULL",
        )
        self.assertEqual(text(rows[0], "return_id"), str(new.id))
        await self.returns.save_exit(new.hand_over(NOW))
        unknown = ControlledDatabase(self.database, "unknown")
        parcel = self.delivery()
        with self.assertRaises(PersistenceError):
            await D1DeliveryRepository(lambda: unknown).receive_in_locker(
                parcel, locker.id, DIMS
            )
        self.assertEqual(unknown.calls, 1)
        self.assertIsNotNone(await self.deliveries.get_by_id(parcel.id))

    async def test_exact_maximum_volume_and_timestamp(self) -> None:
        maximum = 2147483647
        locker = await self.lockers.create(
            "large",
            [
                CompartmentBatch(1, Dimensions(maximum, maximum, maximum)),
                CompartmentBatch(1, Dimensions(maximum, maximum, maximum - 2)),
                CompartmentBatch(1, Dimensions(maximum, maximum - 1, maximum - 1)),
            ],
        )
        for kind in ("delivery", "return"):
            with self.subTest(kind=kind):
                current = await self.lockers.get_by_id(locker.id)
                assert current is not None
                expected = select_compartment(current.compartments, Dimensions(1, 1, 1))
                assert expected is not None
                self.database.statements.clear()
                self.database.results.clear()
                selected = await self.receive(kind, locker.id, Dimensions(1, 1, 1))
                self.assert_compact_reception()
                self.assertEqual(selected.compartment_id, expected.id)
                found = await (
                    self.deliveries.get_by_id(selected.id)
                    if kind == "delivery"
                    else self.returns.get_by_id(selected.id)
                )
                self.assertEqual(found, selected)
                self.assertEqual(selected.received_at.microsecond, 123456)

    async def test_occupied_cell_protection_and_return_rollback(self) -> None:
        locker = await self.locker()
        parcel = await self.returns.receive_in_locker(
            self.parcel_return(), locker.id, DIMS
        )
        cell = locker.compartments[0]
        for operation in (
            lambda: self.lockers.retire_compartment(locker.id, cell.id),
            lambda: self.lockers.update_compartment(locker.id, cell.id, enabled=False),
        ):
            with self.assertRaises(CapacityConflictError):
                await operation()
        before = await query(
            self.database, "SELECT revision,mutation_token FROM lockers"
        )
        controlled = ControlledDatabase(self.database, "rollback")
        with self.assertRaises(PersistenceError):
            await D1ReturnRepository(lambda: controlled).save_exit(
                parcel.hand_over(NOW + timedelta(seconds=1))
            )
        self.assertEqual(
            await query(self.database, "SELECT revision,mutation_token FROM lockers"),
            before,
        )
        self.assertEqual(await self.returns.get_by_id(parcel.id), parcel)
        self.assertTrue(await self.returns.save_exit(parcel.hand_over(NOW)))
