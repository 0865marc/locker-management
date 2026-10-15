"""Real PostgreSQL checks in a unique disposable schema, never in public tables."""
import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import FastAPI
import httpx
from sqlalchemy import event, text

from adapters.database.sqlmodel_repositories import SqlModelDeliveryRepository, SqlModelReturnRepository
from adapters.http.routes import create_router
from application.use_cases import DeliveryService, ReturnService
from domain.models import Delivery, Return

from tests.integration.support import PostgresTestCase
NOW = datetime(2026, 10, 14, 12, 30, 25, 123456, tzinfo=timezone.utc)


class PostgreSQLCustodyTests(PostgresTestCase):
    async def test_concurrent_repository_exits_commit_exactly_one_winner(self):
        examples = [
            (Delivery(tracking_number="D-1", carrier_code="carrier-a", recipient_name="Ana", received_at=NOW), SqlModelDeliveryRepository, "collect", "return_to_carrier"),
            (Return(tracking_number="R-1", carrier_code="carrier-a", received_at=NOW), SqlModelReturnRepository, "hand_over", "hand_over"),
        ]
        for original, repository_class, first, second in examples:
            repositories = [repository_class(self.database()[1]) for _ in range(2)]
            await repositories[0].save(original)
            # Both independent reads finish before either conditional UPDATE starts.
            snapshots = await asyncio.gather(*(repo.get_by_id(original.id) for repo in repositories))
            contenders = [getattr(snapshots[0], first)(NOW + timedelta(seconds=1)),
                          getattr(snapshots[1], second)(NOW + timedelta(seconds=2))]
            results = await asyncio.gather(*(repo.save_exit(item) for repo, item in zip(repositories, contenders)))
            self.assertCountEqual(results, [True, False])
            winner = contenders[results.index(True)]
            self.assertEqual(await repository_class(self.sessions).get_by_id(original.id), winner)
            self.assertFalse(await repositories[results.index(False)].save_exit(contenders[results.index(False)]))
            self.assertEqual(await repositories[0].get_by_id(original.id), winner)

    async def test_concurrent_http_exits_return_200_and_409_and_preserve_winner(self):
        for kind in ("delivery", "return"):
            repository_class = SqlModelDeliveryRepository if kind == "delivery" else SqlModelReturnRepository
            original = (Delivery(tracking_number="D-http", carrier_code="carrier-a", recipient_name="Ana", received_at=NOW)
                        if kind == "delivery" else Return(tracking_number="R-http", carrier_code="carrier-a", received_at=NOW))
            await repository_class(self.sessions).save(original)
            both_read = asyncio.Event()
            read_count = 0

            class SynchronizedRepository(repository_class):
                async def get_by_id(inner, identifier):
                    nonlocal read_count
                    item = await super().get_by_id(identifier)
                    read_count += 1
                    if read_count == 2:
                        both_read.set()
                    await asyncio.wait_for(both_read.wait(), timeout=10)
                    return item

            clients = []
            try:
                for seconds in (1, 2):
                    _, sessions = self.database()
                    delivery_repo = SynchronizedRepository(sessions) if kind == "delivery" else SqlModelDeliveryRepository(sessions)
                    return_repo = SynchronizedRepository(sessions) if kind == "return" else SqlModelReturnRepository(sessions)
                    clock = lambda seconds=seconds: NOW + timedelta(seconds=seconds)
                    app = FastAPI()
                    app.include_router(create_router(DeliveryService(delivery_repo, clock=clock), ReturnService(return_repo, clock=clock)))
                    clients.append(httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test"))
                paths = ([f"/deliveries/{original.id}/collect", f"/deliveries/{original.id}/return-to-carrier"]
                         if kind == "delivery" else [f"/returns/{original.id}/hand-over"] * 2)
                responses = await asyncio.gather(*(client.post(path) for client, path in zip(clients, paths)))
                self.assertCountEqual([response.status_code for response in responses], [200, 409])
                winner = next(response.json() for response in responses if response.status_code == 200)
                listing = await clients[0].get("/deliveries" if kind == "delivery" else "/returns")
                self.assertEqual(listing.status_code, 200)
                self.assertIn(winner, listing.json())
            finally:
                await asyncio.gather(*(client.aclose() for client in clients))

    async def test_migration_empty_round_trip_has_timezone_columns_and_constraints(self):
        original = await self.snapshot()
        for table in ("deliveries", "returns"):
            columns, constraints, *_ = original[0][table]
            self.assertTrue(constraints)
            self.assertTrue(all(column["type"] == "TIMESTAMP" for column in columns if column["name"].endswith("_at")))
        async with self.engine.connect() as connection:
            aware = (await connection.execute(text("SELECT data_type FROM information_schema.columns WHERE table_schema = :schema AND column_name LIKE '%\\_at' ESCAPE '\\'"), {"schema": self.schema})).scalars().all()
            self.assertTrue(aware)
            self.assertEqual(set(aware), {"timestamp with time zone"})
        await self.migrate("downgrade", "0001")
        await self.migrate("upgrade", "head")
        self.assertEqual(await self.snapshot(), original)
        await self.migrate("downgrade", "base")
        await self.migrate("upgrade", "head")
        self.assertEqual(await self.snapshot(), original)

    async def test_populated_migrations_preserve_rows_schema_revision_and_lock_first(self):
        for tables in [("deliveries",), ("returns",), ("deliveries", "returns")]:
            await self.migrate("downgrade", "0001")
            async with self.engine.begin() as connection:
                for table in tables:
                    field = "address" if table == "deliveries" else "reason"
                    await connection.execute(text(f"INSERT INTO {table} (id, {field}) VALUES (:id, :value)"), {"id": uuid4(), "value": "Preserved legacy data"})
            before = await self.snapshot()
            statements = []
            def record(connection, cursor, statement, parameters, context, executemany):
                statements.append(statement)
            event.listen(self.engine.sync_engine, "before_cursor_execute", record)
            try:
                with self.assertRaisesRegex(RuntimeError, "explicit data migration"):
                    await self.migrate("upgrade", "head")
            finally:
                event.remove(self.engine.sync_engine, "before_cursor_execute", record)
            self.assertEqual(await self.snapshot(), before)
            lock = next(i for i, sql in enumerate(statements) if sql.startswith("LOCK TABLE deliveries, returns IN ACCESS EXCLUSIVE MODE"))
            row_check = next(i for i, sql in enumerate(statements) if sql.startswith("SELECT 1 FROM deliveries"))
            self.assertLess(lock, row_check)
            async with self.engine.begin() as connection:
                # Delete only test rows in this test's freshly-created private schema.
                for table in tables:
                    await connection.execute(text(f"DELETE FROM {table}"))
            await self.migrate("upgrade", "head")
            async with self.engine.begin() as connection:
                for table in tables:
                    columns = "id, tracking_number, carrier_code, received_at, status"
                    values = ":id, 'PKG-42', 'carrier-a', :received, :status"
                    if table == "deliveries":
                        columns += ", recipient_name"
                        values += ", 'Ana'"
                    await connection.execute(text(f"INSERT INTO {table} ({columns}) VALUES ({values})"), {"id": uuid4(), "received": NOW, "status": "AWAITING_PICKUP" if table == "deliveries" else "AWAITING_CARRIER"})
            await self.migrate("downgrade", "0002")
            before = await self.snapshot()
            statements.clear()
            event.listen(self.engine.sync_engine, "before_cursor_execute", record)
            try:
                with self.assertRaisesRegex(RuntimeError, "would lose parcel custody data"):
                    await self.migrate("downgrade", "0001")
            finally:
                event.remove(self.engine.sync_engine, "before_cursor_execute", record)
            self.assertEqual(await self.snapshot(), before)
            self.assertTrue(any(sql.startswith("LOCK TABLE deliveries, returns IN ACCESS EXCLUSIVE MODE") for sql in statements))
            async with self.engine.begin() as connection:
                for table in tables:
                    await connection.execute(text(f"DELETE FROM {table}"))

    async def populate_current_parcels(self):
        deliveries = SqlModelDeliveryRepository(self.sessions)
        returns = SqlModelReturnRepository(self.sessions)
        for index, transition in enumerate((None, "collect", "return_to_carrier")):
            item = Delivery(tracking_number=f"D-{index}", carrier_code="carrier-a",
                            recipient_name="Ana", recipient_phone="600123456",
                            pickup_deadline_at=NOW + timedelta(days=1), received_at=NOW)
            await deliveries.save(getattr(item, transition)(NOW + timedelta(seconds=1)) if transition else item)
        for index, terminal in enumerate((False, True)):
            item = Return(tracking_number=f"R-{index}", carrier_code="carrier-b", sender_name="Luis", received_at=NOW)
            await returns.save(item.hand_over(NOW + timedelta(seconds=1)) if terminal else item)

    async def test_populated_0002_upgrade_adds_only_empty_locker_storage_and_round_trips(self):
        await self.migrate("downgrade", "0002")
        await self.populate_current_parcels()
        before = await self.snapshot()
        await self.migrate("upgrade", "head")
        current = await self.snapshot()
        self.assertEqual(current[1]["alembic_version"], [("0003",)])
        for table in ("deliveries", "returns"):
            self.assertEqual(current[0][table], before[0][table])
            self.assertEqual(current[1][table], before[1][table])
        for table in ("lockers", "locker_compartments", "locker_assignments"):
            self.assertEqual(current[1][table], [])
        await self.migrate("check")
        await self.migrate("downgrade", "0002")
        self.assertEqual(await self.snapshot(), before)
        await self.migrate("upgrade", "head")
        self.assertEqual(await self.snapshot(), current)

    async def test_populated_locker_downgrade_preserves_full_schema_and_history(self):
        from adapters.database.sqlmodel_lockers import SqlModelLockerRepository
        from domain.lockers import CompartmentBatch, Dimensions

        lockers = SqlModelLockerRepository(self.sessions)
        locker = await lockers.create("MAD-01", [CompartmentBatch(1, Dimensions(100, 200, 300))])
        before = await self.snapshot()
        with self.assertRaisesRegex(RuntimeError, "(?i)(locker|custody|data)"):
            await self.migrate("downgrade", "0002")
        self.assertEqual(await self.snapshot(), before)

        original = Delivery(tracking_number="HISTORY", carrier_code="carrier-a", recipient_name="Ana", received_at=NOW)
        deliveries = SqlModelDeliveryRepository(self.sessions)
        assigned = await deliveries.receive_in_locker(original, locker.id, Dimensions(10, 20, 30))
        for released in (False, True):
            if released:
                self.assertTrue(await deliveries.save_exit(assigned.collect(NOW + timedelta(seconds=1))))
                await lockers.retire_compartment(locker.id, assigned.compartment_id)
            before = await self.snapshot()
            statements = []
            def record(connection, cursor, statement, parameters, context, executemany):
                statements.append(statement)
            event.listen(self.engine.sync_engine, "before_cursor_execute", record)
            try:
                with self.assertRaisesRegex(RuntimeError, "(?i)(locker|custody|data)"):
                    await self.migrate("downgrade", "0002")
            finally:
                event.remove(self.engine.sync_engine, "before_cursor_execute", record)
            self.assertEqual(await self.snapshot(), before)
            lock = next(i for i, sql in enumerate(statements)
                        if sql.startswith("LOCK TABLE") and "locker" in sql)
            check = next(i for i, sql in enumerate(statements)
                         if sql.startswith("SELECT 1 FROM locker"))
            self.assertLess(lock, check)
            self.assertFalse(any(sql.lstrip().upper().startswith(("DROP ", "ALTER ", "DELETE "))
                                 for sql in statements))
