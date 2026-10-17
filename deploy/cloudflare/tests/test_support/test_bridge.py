"""Transport guarantees using official local D1, independently of domain SQL."""

import asyncio
import tempfile
import unittest
from pathlib import Path

from native_d1 import NativeD1

from adapters.database.d1.bindings import D1BindingError


class BridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_atomic_batch_failure_and_no_transport_retry(self) -> None:
        async with NativeD1() as database:
            await database.exec("CREATE TABLE sample(n INTEGER CHECK(n > 0));")
            await database.prepare("INSERT INTO sample VALUES (?)").bind(1).run()
            with self.assertRaises(D1BindingError):
                await database.batch(
                    [
                        database.prepare("INSERT INTO sample VALUES (?)").bind(2),
                        database.prepare("INSERT INTO sample VALUES (?)").bind(-1),
                    ]
                )
            self.assertEqual(
                await database.prepare("SELECT n FROM sample").first(), {"n": 1}
            )
            self.assertEqual(len(database.statements), 4)

    async def test_concurrent_inserts_constraint_and_isolated_state(self) -> None:
        async with NativeD1() as first, NativeD1() as second:
            for database in (first, second):
                await database.exec("CREATE TABLE sample(n INTEGER UNIQUE);")
            results = await asyncio.gather(
                first.prepare("INSERT INTO sample VALUES (?)").bind(1).run(),
                first.prepare("INSERT INTO sample VALUES (?)").bind(1).run(),
                return_exceptions=True,
            )
            self.assertEqual(
                sum(isinstance(result, D1BindingError) for result in results), 1
            )
            self.assertEqual(
                await second.prepare("SELECT COUNT(*) AS n FROM sample").first(),
                {"n": 0},
            )
            self.assertEqual(
                await first.prepare("SELECT COUNT(*) AS n FROM sample").first(),
                {"n": 1},
            )

    async def test_bounds_rejected_and_cleanup_on_exception(self) -> None:
        database = NativeD1()
        with self.assertRaisesRegex(ValueError, "test cleanup"):
            async with database:
                with self.assertRaises(D1BindingError):
                    await database.prepare("SELECT ?").bind(*range(101)).all()
                raise ValueError("test cleanup")
        self.assertIsNone(database.process)
        with self.assertRaises(D1BindingError):
            await database.prepare("SELECT 1").all()

    async def test_populated_storage_reopens_after_workerd_process_restart(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="locker-reopen-") as state:
            directory = Path(state)
            async with NativeD1(directory) as first:
                await first.migrate()
                await first.exec("CREATE TABLE reopen_marker(value TEXT NOT NULL);")
                await (
                    first.prepare("INSERT INTO reopen_marker VALUES (?)")
                    .bind("preserved")
                    .run()
                )
                history = await first.prepare(
                    "SELECT group_concat(name) AS names FROM d1_migrations ORDER BY id"
                ).first()
            self.assertTrue(directory.is_dir())
            async with NativeD1(directory) as reopened:
                await reopened.migrate()
                self.assertEqual(
                    await reopened.prepare("SELECT value FROM reopen_marker").first(),
                    {"value": "preserved"},
                )
                self.assertEqual(
                    await reopened.prepare(
                        "SELECT group_concat(name) AS names FROM d1_migrations ORDER BY id"
                    ).first(),
                    history,
                )
            self.assertTrue(directory.is_dir())
