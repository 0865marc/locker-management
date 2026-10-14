"""El historial de Alembic crea y revierte el esquema definido por SQLModel."""

import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from alembic import command
from alembic.config import Config


class MigrationTests(unittest.TestCase):
    def test_upgrade_matches_models_and_can_be_reversed(self):
        with TemporaryDirectory() as directory:
            database = Path(directory) / "migrations.db"
            config = Config("alembic.ini")
            with patch.dict(os.environ, {"DATABASE_URL": f"sqlite+aiosqlite:///{database}"}):
                command.upgrade(config, "head")
                command.check(config)
                with sqlite3.connect(database) as connection:
                    self.assertEqual(
                        connection.execute("SELECT version_num FROM alembic_version").fetchone(),
                        ("0001",),
                    )
                    tables = {
                        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    }
                    self.assertTrue({"deliveries", "returns"}.issubset(tables))

                command.downgrade(config, "base")
                with sqlite3.connect(database) as connection:
                    tables = {
                        row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")
                    }
                    self.assertFalse({"deliveries", "returns"} & tables)

                command.upgrade(config, "head")
                command.check(config)
