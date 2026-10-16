"""PostgreSQL capacity races with independent connections and observed database locks."""

import asyncio
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import httpx
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError

from adapters.database.sqlmodel_deliveries import SqlModelDeliveryRepository
from adapters.database.sqlmodel_lockers import SqlModelLockerRepository
from adapters.database.sqlmodel_returns import SqlModelReturnRepository
from domain.deliveries import Delivery
from domain.lockers import CompartmentBatch, Dimensions, Locker
from domain.returns import Return
from tests.integration.support import PostgresTestCase

NOW = datetime(2026, 10, 14, 12, 30, 25, 123456, tzinfo=timezone.utc)
DIMENSIONS = {"width_mm": 100, "height_mm": 200, "depth_mm": 300}


class StatementGate:
    """Pause after an executed statement; timeout is only a deadlock safeguard."""

    def __init__(self, engine, pattern="FOR UPDATE", fail=False):
        self.acquired = asyncio.Event()
        self.release = asyncio.Event()
        self.pid = None
        self.used = False
        self.fail = fail
        self.engine = engine
        self.pattern = pattern
        event.listen(engine.sync_engine, "after_cursor_execute", self.after)

    def after(self, connection, cursor, statement, parameters, context, executemany):
        if self.used or self.pattern not in statement:
            return
        self.used = True
        self.pid = connection.connection.driver_connection.get_server_pid()
        self.acquired.set()

        async def hold(driver_connection):
            await asyncio.wait_for(self.release.wait(), 15)
            if self.fail:
                raise RuntimeError(
                    "injected failure after executed write before commit"
                )

        connection.connection.dbapi_connection.run_async(hold)

    def close(self):
        self.release.set()
        event.remove(self.engine.sync_engine, "after_cursor_execute", self.after)


class PostgreSQLLockerTests(PostgresTestCase):
    def responses(
        self, results: Sequence[httpx.Response | BaseException]
    ) -> list[httpx.Response]:
        responses: list[httpx.Response] = []
        for result in results:
            assert isinstance(result, httpx.Response), result
            responses.append(result)
        return responses

    async def current_locker(self, identifier: UUID) -> Locker:
        locker = await self.lockers.get_by_id(identifier)
        assert locker is not None
        return locker

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.lockers = SqlModelLockerRepository(self.sessions)

    async def locker(self, quantity=1):
        return await self.lockers.create(
            "MAD-01", [CompartmentBatch(quantity, Dimensions(**DIMENSIONS))]
        )

    def receive(self, client, kind, locker_id, tracking="PARCEL"):
        payload = {
            "tracking_number": tracking,
            "carrier_code": "carrier-a",
            "locker_id": str(locker_id),
            "parcel_dimensions": DIMENSIONS,
        }
        if kind == "deliveries":
            payload["recipient_name"] = "Ana"
        return client.post(f"/{kind}", json=payload)

    async def counts(self):
        async with self.engine.connect() as connection:
            return tuple(
                [
                    (
                        await connection.execute(text(f"SELECT count(*) FROM {table}"))
                    ).scalar_one()
                    for table in ("deliveries", "returns", "locker_assignments")
                ]
            )

    async def competing(
        self,
        first_engine,
        first_operation,
        second_engine,
        second_operation,
        pattern="FOR UPDATE",
        fail=False,
    ):
        """Prove the second backend is blocked by the first before releasing it."""
        gate = StatementGate(first_engine, pattern, fail)
        attempting = asyncio.Event()
        second_pid = None

        def before(connection, cursor, statement, parameters, context, executemany):
            nonlocal second_pid
            if "FOR UPDATE" in statement:
                second_pid = connection.connection.driver_connection.get_server_pid()
                attempting.set()

        event.listen(second_engine.sync_engine, "before_cursor_execute", before)
        first = asyncio.create_task(first_operation())
        second = None
        try:
            await asyncio.wait_for(gate.acquired.wait(), 15)
            second = asyncio.create_task(second_operation())
            await asyncio.wait_for(attempting.wait(), 15)
            self.assertNotEqual(second_pid, gate.pid)
            async with asyncio.timeout(15):
                async with self.admin.connect() as connection:
                    while True:
                        blockers = (
                            await connection.execute(
                                text("SELECT pg_blocking_pids(:pid)"),
                                {"pid": second_pid},
                            )
                        ).scalar_one()
                        if gate.pid in blockers:
                            break
            gate.release.set()
            return await asyncio.gather(first, second, return_exceptions=True)
        finally:
            gate.close()
            event.remove(second_engine.sync_engine, "before_cursor_execute", before)
            pending = [
                task for task in (first, second) if task is not None and not task.done()
            ]
            for task in pending:
                task.cancel()
            if pending:
                await asyncio.gather(*pending, return_exceptions=True)

    async def test_delivery_and_return_share_last_cell_after_committed_winner(self):
        for first_kind, second_kind in (
            ("deliveries", "returns"),
            ("returns", "deliveries"),
        ):
            with self.subTest(first_kind=first_kind):
                locker = await self.locker()
                first, first_engine = await self.actor()
                second, second_engine = await self.actor()
                before = await self.counts()
                responses = await self.competing(
                    first_engine,
                    lambda: self.receive(first, first_kind, locker.id, "WINNER"),
                    second_engine,
                    lambda: self.receive(second, second_kind, locker.id, "LOSER"),
                )
                responses = self.responses(responses)
                self.assertEqual([r.status_code for r in responses], [201, 409])
                self.assertEqual(responses[1].json()["detail"]["code"], "FULL")
                winner = responses[0].json()
                self.assertEqual(
                    winner["compartment_id"], str(locker.compartments[0].id)
                )
                after = await self.counts()
                self.assertEqual(
                    tuple(a - b for a, b in zip(after, before)),
                    (1, 0, 1) if first_kind == "deliveries" else (0, 1, 1),
                )
                listing = await second.get(f"/{first_kind}")
                self.assertIn(winner, listing.json())
                self.assertTrue(
                    (await self.current_locker(locker.id)).compartments[0].occupied
                )

    async def test_waiter_gets_last_cell_when_first_claimant_rolls_back_both_writes(
        self,
    ):
        for first_kind, second_kind in (
            ("deliveries", "returns"),
            ("returns", "deliveries"),
        ):
            with self.subTest(first_kind=first_kind):
                locker = await self.locker()
                first, first_engine = await self.actor()
                second, second_engine = await self.actor()
                before = await self.counts()
                results = await self.competing(
                    first_engine,
                    lambda: self.receive(first, first_kind, locker.id, "ROLLBACK"),
                    second_engine,
                    lambda: self.receive(second, second_kind, locker.id, "SURVIVOR"),
                    pattern="INSERT INTO locker_assignments",
                    fail=True,
                )
                self.assertIsInstance(results[0], RuntimeError)
                assert isinstance(results[1], httpx.Response)
                self.assertEqual(results[1].status_code, 201)
                self.assertEqual(
                    results[1].json()["compartment_id"], str(locker.compartments[0].id)
                )
                after = await self.counts()
                self.assertEqual(
                    tuple(a - b for a, b in zip(after, before)),
                    (1, 0, 1) if second_kind == "deliveries" else (0, 1, 1),
                )
                self.assertFalse(
                    any(
                        item["tracking_number"] == "ROLLBACK"
                        for item in (await first.get(f"/{first_kind}")).json()
                    )
                )

    async def test_configuration_winner_is_rechecked_by_waiting_reception(self):
        for operation, expected in (
            ("resize", "NO_COMPATIBLE_CELL"),
            ("disable", "NO_COMPATIBLE_CELL"),
            ("retire", "NO_COMPATIBLE_CELL"),
            ("inactive", "LOCKER_INACTIVE"),
        ):
            with self.subTest(operation=operation):
                locker = await self.locker()
                config, config_engine = await self.actor()
                receiver, receive_engine = await self.actor()
                cell_path = (
                    f"/lockers/{locker.id}/compartments/{locker.compartments[0].id}"
                )

                async def configure():
                    if operation == "retire":
                        return await config.delete(cell_path)
                    if operation == "inactive":
                        return await config.patch(
                            f"/lockers/{locker.id}", json={"active": False}
                        )
                    changes = (
                        {"enabled": False}
                        if operation == "disable"
                        else {
                            "dimensions": {"width_mm": 1, "height_mm": 1, "depth_mm": 1}
                        }
                    )
                    return await config.patch(cell_path, json=changes)

                before = await self.counts()
                responses = await self.competing(
                    config_engine,
                    configure,
                    receive_engine,
                    lambda: self.receive(receiver, "deliveries", locker.id),
                )
                responses = self.responses(responses)
                self.assertEqual(
                    responses[0].status_code, 204 if operation == "retire" else 200
                )
                self.assertEqual(responses[1].status_code, 409)
                self.assertEqual(responses[1].json()["detail"]["code"], expected)
                self.assertEqual(await self.counts(), before)

    async def test_reception_winner_protects_cell_from_waiting_configuration(self):
        for operation in ("resize", "disable", "retire", "inactive"):
            with self.subTest(operation=operation):
                locker = await self.locker()
                receiver, receive_engine = await self.actor()
                config, config_engine = await self.actor()
                cell_path = (
                    f"/lockers/{locker.id}/compartments/{locker.compartments[0].id}"
                )

                async def configure():
                    if operation == "retire":
                        return await config.delete(cell_path)
                    if operation == "inactive":
                        return await config.patch(
                            f"/lockers/{locker.id}", json={"active": False}
                        )
                    return await config.patch(
                        cell_path,
                        json={"enabled": False}
                        if operation == "disable"
                        else {
                            "dimensions": {"width_mm": 1, "height_mm": 1, "depth_mm": 1}
                        },
                    )

                responses = await self.competing(
                    receive_engine,
                    lambda: self.receive(receiver, "returns", locker.id),
                    config_engine,
                    configure,
                )
                responses = self.responses(responses)
                self.assertEqual(responses[0].status_code, 201)
                self.assertEqual(
                    responses[1].status_code, 200 if operation == "inactive" else 409
                )
                current = await self.current_locker(locker.id)
                self.assertTrue(current.compartments[0].occupied)
                self.assertTrue(current.compartments[0].enabled)
                self.assertEqual(
                    current.compartments[0].dimensions, Dimensions(**DIMENSIONS)
                )
                if operation == "inactive":
                    self.assertFalse(current.active)
                    exited = await receiver.post(
                        f"/returns/{responses[0].json()['id']}/hand-over"
                    )
                    self.assertEqual(exited.status_code, 200)
                    self.assertFalse(
                        (await self.current_locker(locker.id)).compartments[0].occupied
                    )

    async def test_all_exits_compete_release_once_and_old_exit_cannot_free_new_occupant(
        self,
    ):
        for kind, action in (
            ("deliveries", "collect"),
            ("deliveries", "return-to-carrier"),
            ("returns", "hand-over"),
        ):
            with self.subTest(kind=kind, action=action):
                locker = await self.locker()
                first, first_engine = await self.actor()
                second, second_engine = await self.actor()
                original = (await self.receive(first, kind, locker.id, "A")).json()
                path = f"/{kind}/{original['id']}/{action}"
                results = await self.competing(
                    first_engine,
                    lambda: first.post(path),
                    second_engine,
                    lambda: second.post(path),
                )
                results = self.responses(results)
                self.assertEqual([r.status_code for r in results], [200, 409])
                completed = results[0].json()
                self.assertFalse(
                    (await self.current_locker(locker.id)).compartments[0].occupied
                )
                replacement = (
                    await self.receive(second, "returns", locker.id, "B")
                ).json()
                self.assertEqual(
                    replacement["compartment_id"], original["compartment_id"]
                )
                self.assertEqual((await second.post(path)).status_code, 409)
                self.assertTrue(
                    (await self.current_locker(locker.id)).compartments[0].occupied
                )
                self.assertIn(completed, (await first.get(f"/{kind}")).json())
                self.assertIn(replacement, (await first.get("/returns")).json())
                async with self.engine.connect() as connection:
                    active = (
                        await connection.execute(
                            text(
                                "SELECT return_id FROM locker_assignments WHERE compartment_id=:cell AND released_at IS NULL"
                            ),
                            {"cell": UUID(replacement["compartment_id"])},
                        )
                    ).scalar_one()
                    self.assertEqual(active, UUID(replacement["id"]))

    async def test_each_exit_rollback_preserves_pending_parcel_and_active_assignment(
        self,
    ):
        for kind, action, pending in (
            ("deliveries", "collect", "AWAITING_PICKUP"),
            ("deliveries", "return-to-carrier", "AWAITING_PICKUP"),
            ("returns", "hand-over", "AWAITING_CARRIER"),
        ):
            with self.subTest(action=action):
                locker = await self.locker()
                client, engine = await self.actor()
                original = (await self.receive(client, kind, locker.id)).json()
                gate = StatementGate(engine, "UPDATE locker_assignments", fail=True)
                gate.release.set()
                try:
                    with self.assertRaisesRegex(RuntimeError, "injected failure"):
                        await client.post(f"/{kind}/{original['id']}/{action}")
                finally:
                    gate.close()
                self.assertTrue(
                    gate.used, "Failure must follow the actual release write"
                )
                self.assertIn(original, (await client.get(f"/{kind}")).json())
                self.assertEqual(original["status"], pending)
                self.assertTrue(
                    (await self.current_locker(locker.id)).compartments[0].occupied
                )
                self.assertEqual(
                    (
                        await client.post(f"/{kind}/{original['id']}/{action}")
                    ).status_code,
                    200,
                )
                self.assertFalse(
                    (await self.current_locker(locker.id)).compartments[0].occupied
                )

    async def test_same_uuid_parcels_and_historical_assignment_survive_resize_and_retirement(
        self,
    ):
        locker = await self.locker(2)
        deliveries = SqlModelDeliveryRepository(self.sessions)
        returns = SqlModelReturnRepository(self.sessions)
        identifier = uuid4()
        parcel_dimensions = Dimensions(30, 20, 10)
        delivery = await deliveries.receive_in_locker(
            Delivery(
                id=identifier,
                tracking_number="SAME-D",
                carrier_code="carrier-a",
                recipient_name="Ana",
                received_at=NOW,
            ),
            locker.id,
            parcel_dimensions,
        )
        returned = await returns.receive_in_locker(
            Return(
                id=identifier,
                tracking_number="SAME-R",
                carrier_code="carrier-a",
                received_at=NOW,
            ),
            locker.id,
            parcel_dimensions,
        )
        assert delivery.compartment_id is not None
        assert returned.compartment_id is not None
        self.assertNotEqual(delivery.compartment_id, returned.compartment_id)
        self.assertEqual(await deliveries.get_by_id(identifier), delivery)
        self.assertEqual(await returns.get_by_id(identifier), returned)
        await self.lockers.set_active(locker.id, False)
        completed_delivery = delivery.collect(NOW + timedelta(seconds=1))
        self.assertTrue(await deliveries.save_exit(completed_delivery))
        self.assertEqual(await returns.get_by_id(identifier), returned)
        current = await self.current_locker(locker.id)
        self.assertTrue(
            next(
                c for c in current.compartments if c.id == returned.compartment_id
            ).occupied
        )
        await self.lockers.update_compartment(
            locker.id, delivery.compartment_id, Dimensions(1, 2, 3)
        )
        await self.lockers.retire_compartment(locker.id, delivery.compartment_id)
        self.assertEqual(await deliveries.get_by_id(identifier), completed_delivery)
        completed_return = returned.hand_over(NOW + timedelta(seconds=2))
        self.assertTrue(await returns.save_exit(completed_return))
        await self.lockers.update_compartment(
            locker.id, returned.compartment_id, Dimensions(4, 5, 6)
        )
        await self.lockers.retire_compartment(locker.id, returned.compartment_id)
        self.assertEqual(await returns.get_by_id(identifier), completed_return)
        self.assertEqual((await self.current_locker(locker.id)).compartments, ())

    async def test_database_constraints_enforce_shared_capacity_and_references(self):
        locker = await self.locker(2)
        deliveries = SqlModelDeliveryRepository(self.sessions)
        returns = SqlModelReturnRepository(self.sessions)
        delivery = await deliveries.receive_in_locker(
            Delivery(
                tracking_number="D",
                carrier_code="c",
                recipient_name="Ana",
                received_at=NOW,
            ),
            locker.id,
            Dimensions(10, 20, 30),
        )
        returned = await returns.receive_in_locker(
            Return(tracking_number="R", carrier_code="c", received_at=NOW),
            locker.id,
            Dimensions(10, 20, 30),
        )
        statements = [
            (
                "UPDATE locker_assignments SET return_id=:return_id WHERE delivery_id=:delivery_id",
                {},
            ),
            (
                "UPDATE locker_assignments SET delivery_id=NULL WHERE delivery_id=:delivery_id",
                {},
            ),
            (
                "UPDATE locker_assignments SET compartment_id=:occupied WHERE return_id=:return_id",
                {},
            ),
            (
                "UPDATE locker_assignments SET delivery_id=:delivery_id, return_id=NULL WHERE return_id=:return_id",
                {},
            ),
            (
                "UPDATE locker_assignments SET return_id=:return_id, delivery_id=NULL WHERE delivery_id=:delivery_id",
                {},
            ),
            (
                "UPDATE locker_assignments SET compartment_id=:missing WHERE delivery_id=:delivery_id",
                {},
            ),
            (
                "UPDATE locker_assignments SET delivery_id=:missing WHERE delivery_id=:delivery_id",
                {},
            ),
            (
                "UPDATE locker_assignments SET return_id=:missing WHERE return_id=:return_id",
                {},
            ),
            (
                "UPDATE locker_assignments SET width_mm=0 WHERE delivery_id=:delivery_id",
                {},
            ),
            (
                "UPDATE locker_assignments SET released_at=:earlier WHERE delivery_id=:delivery_id",
                {},
            ),
            ("UPDATE locker_compartments SET depth_mm=0 WHERE id=:occupied", {}),
            (
                "UPDATE locker_compartments SET retired=true, enabled=true WHERE id=:occupied",
                {},
            ),
            (
                "UPDATE locker_compartments SET locker_id=:missing WHERE id=:occupied",
                {},
            ),
            ("DELETE FROM lockers WHERE id=:locker_id", {}),
            ("DELETE FROM locker_compartments WHERE id=:occupied", {}),
            ("DELETE FROM deliveries WHERE id=:delivery_id", {}),
            ("DELETE FROM returns WHERE id=:return_id", {}),
        ]
        parameters = {
            "delivery_id": delivery.id,
            "return_id": returned.id,
            "occupied": delivery.compartment_id,
            "locker_id": locker.id,
            "missing": uuid4(),
            "earlier": NOW - timedelta(microseconds=1),
        }
        for sql, additions in statements:
            with self.subTest(sql=sql):
                with self.assertRaises(IntegrityError):
                    async with self.engine.begin() as connection:
                        await connection.execute(text(sql), parameters | additions)
                self.assertEqual(await deliveries.get_by_id(delivery.id), delivery)
                self.assertEqual(await returns.get_by_id(returned.id), returned)
