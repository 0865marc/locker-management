"""Alembic history and non-destructive migration guards on SQLite."""
from contextlib import closing
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from alembic import command
from alembic.config import Config


class MigrationTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.database = Path(self.directory.name) / "migrations.db"
        self.environment = patch.dict(os.environ, {"DATABASE_URL": f"sqlite+aiosqlite:///{self.database}"})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.config = Config("alembic.ini")

    def snapshot(self):
        with closing(sqlite3.connect(self.database)) as connection, connection:
            return {
                "schema": connection.execute("SELECT name, sql FROM sqlite_master WHERE type='table' ORDER BY name").fetchall(),
                "revision": connection.execute("SELECT * FROM alembic_version").fetchall(),
                "deliveries": connection.execute("SELECT * FROM deliveries").fetchall(),
                "returns": connection.execute("SELECT * FROM returns").fetchall(),
            }

    def test_initial_revision_retains_legacy_columns(self):
        command.upgrade(self.config, "0001")
        with closing(sqlite3.connect(self.database)) as connection, connection:
            self.assertEqual([r[1] for r in connection.execute("PRAGMA table_info(deliveries)")], ["id", "address"])
            self.assertEqual([r[1] for r in connection.execute("PRAGMA table_info(returns)")], ["id", "reason"])
        self.assertEqual(self.snapshot()["revision"], [("0001",)])

    def test_empty_round_trip_and_current_schema_match_models(self):
        command.upgrade(self.config, "head")
        command.check(self.config)
        current = self.snapshot()
        self.assertEqual(current["revision"], [("0002",)])
        command.downgrade(self.config, "0001")
        self.assertEqual(self.snapshot()["revision"], [("0001",)])
        command.upgrade(self.config, "head")
        command.check(self.config)
        self.assertEqual(self.snapshot(), current)
        command.downgrade(self.config, "base")
        with closing(sqlite3.connect(self.database)) as connection, connection:
            tables = {r[0] for r in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            self.assertFalse({"deliveries", "returns"} & tables)
        command.upgrade(self.config, "head")
        command.check(self.config)

    def test_populated_legacy_tables_block_upgrade_before_any_change(self):
        for tables in [("deliveries",), ("returns",), ("deliveries", "returns")]:
            with self.subTest(tables=tables):
                if self.database.exists():
                    self.database.unlink()
                command.upgrade(self.config, "0001")
                with closing(sqlite3.connect(self.database)) as connection, connection:
                    for table in tables:
                        connection.execute(f"INSERT INTO {table} VALUES (?, ?)", ("a" * 32, "Preserve this real value"))
                before = self.snapshot()
                with self.assertRaisesRegex(RuntimeError, "explicit data migration") as error:
                    command.upgrade(self.config, "head")
                for table in tables:
                    self.assertIn(table, str(error.exception))
                self.assertIn("lack required", str(error.exception))
                self.assertEqual(self.snapshot(), before)

    def test_populated_parcel_tables_block_downgrade_before_any_change(self):
        for tables in [("deliveries",), ("returns",), ("deliveries", "returns")]:
            with self.subTest(tables=tables):
                if self.database.exists():
                    self.database.unlink()
                command.upgrade(self.config, "head")
                with closing(sqlite3.connect(self.database)) as connection, connection:
                    for table in tables:
                        columns = "id, tracking_number, carrier_code, received_at, status"
                        values = ["a" * 32, "PKG-42", "carrier-a", "2026-10-14 12:30:25.123456", "AWAITING_PICKUP" if table == "deliveries" else "AWAITING_CARRIER"]
                        if table == "deliveries":
                            columns += ", recipient_name"
                            values.append("Ana")
                        connection.execute(f"INSERT INTO {table} ({columns}) VALUES ({','.join('?' for _ in values)})", values)
                before = self.snapshot()
                with self.assertRaisesRegex(RuntimeError, "would lose parcel custody data"):
                    command.downgrade(self.config, "0001")
                self.assertEqual(self.snapshot(), before)
