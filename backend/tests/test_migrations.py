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
            tables = [row[0] for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")]
            return {
                "schema": connection.execute(
                    "SELECT type, name, tbl_name, sql FROM sqlite_master "
                    "WHERE type IN ('table', 'index', 'trigger') ORDER BY type, name").fetchall(),
                "rows": {table: connection.execute(f'SELECT * FROM "{table}" ORDER BY 1').fetchall()
                         for table in tables},
                "revision": connection.execute("SELECT * FROM alembic_version").fetchall(),
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
        self.assertEqual(current["revision"], [("0003",)])
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
                command.upgrade(self.config, "0002")
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

    def populate_current_parcels(self):
        """Pending and terminal fixtures exercise every existing custody field."""
        with closing(sqlite3.connect(self.database)) as connection, connection:
            for index, status in enumerate(("AWAITING_PICKUP", "COLLECTED", "RETURNED_TO_CARRIER")):
                connection.execute(
                    "INSERT INTO deliveries VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (f"{index + 1:032x}", f"D-{index}", "carrier-a", "Ana", "600123456",
                     "2026-10-14 12:30:25.123456", "2026-10-20 16:00:00.000000", status,
                     "2026-10-15 12:30:25.123456" if status == "COLLECTED" else None,
                     "2026-10-15 12:30:25.123456" if status == "RETURNED_TO_CARRIER" else None))
            for index, status in enumerate(("AWAITING_CARRIER", "HANDED_OVER")):
                connection.execute(
                    "INSERT INTO returns VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (f"{index + 1:032x}", f"R-{index}", "carrier-b", "Luis",
                     "2026-10-14 12:30:25.123456", status,
                     "2026-10-15 12:30:25.123456" if status == "HANDED_OVER" else None))

    def test_populated_0002_upgrade_is_additive_and_empty_locker_downgrade_preserves_parcels(self):
        command.upgrade(self.config, "0002")
        self.populate_current_parcels()
        original = self.snapshot()
        command.upgrade(self.config, "head")
        command.check(self.config)
        current = self.snapshot()
        self.assertEqual(current["revision"], [("0003",)])
        for table in ("deliveries", "returns"):
            self.assertEqual(current["rows"][table], original["rows"][table])
            self.assertEqual([item for item in current["schema"] if item[2] == table],
                             [item for item in original["schema"] if item[2] == table])
        for table in ("lockers", "locker_compartments", "locker_assignments"):
            self.assertEqual(current["rows"][table], [])
        command.downgrade(self.config, "0002")
        self.assertEqual(self.snapshot(), original)
        command.upgrade(self.config, "head")
        self.assertEqual(self.snapshot(), current)

    def test_locker_downgrade_preserves_configuration_and_released_retired_history(self):
        for state in ("locker", "cell", "active", "historical"):
            with self.subTest(state=state):
                if self.database.exists():
                    self.database.unlink()
                command.upgrade(self.config, "head")
                self.populate_current_parcels()
                with closing(sqlite3.connect(self.database)) as connection, connection:
                    connection.execute("PRAGMA foreign_keys=ON")
                    connection.execute("INSERT INTO lockers (id, location_id, active) VALUES (?, ?, ?)",
                                       ("a" * 32, "MAD-01", True))
                    if state != "locker":
                        connection.execute(
                            "INSERT INTO locker_compartments "
                            "(id, locker_id, width_mm, height_mm, depth_mm, enabled, retired) "
                            "VALUES (?, ?, 100, 200, 300, ?, ?)",
                            ("b" * 32, "a" * 32, state != "historical", state == "historical"))
                    if state in ("active", "historical"):
                        connection.execute(
                            "INSERT INTO locker_assignments "
                            "(id, compartment_id, delivery_id, width_mm, height_mm, depth_mm, assigned_at, released_at) "
                            "VALUES (?, ?, ?, 10, 20, 30, ?, ?)",
                            ("c" * 32, "b" * 32, f"{1 if state == 'active' else 2:032x}",
                             "2026-10-14 12:30:25.123456",
                             "2026-10-15 12:30:25.123456" if state == "historical" else None))
                before = self.snapshot()
                with self.assertRaisesRegex(RuntimeError, "(?i)(locker|custody|data)"):
                    command.downgrade(self.config, "0002")
                self.assertEqual(self.snapshot(), before)
