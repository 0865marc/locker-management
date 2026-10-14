"""Persistencia y transacciones de SQLModel sobre una BD temporal en memoria."""

import unittest

from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel

from adapters.database.connection import create_database
from adapters.database.sqlmodel_repositories import (
    SqlModelDeliveryRepository,
    SqlModelReturnRepository,
)
from domain.models import Delivery, Return


REPOSITORIES = (
    (Delivery, SqlModelDeliveryRepository),
    (Return, SqlModelReturnRepository),
)


class RepositoryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine, self.sessions = create_database("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as connection:
            await connection.run_sync(SQLModel.metadata.create_all)

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_save_and_list_persist_domain_models(self):
        for model, repository_class in REPOSITORIES:
            with self.subTest(repository=repository_class.__name__):
                repository = repository_class(self.sessions)
                self.assertEqual(await repository.list_all(), [])
                expected = [model("Primero"), model("Segundo")]
                for item in expected:
                    await repository.save(item)
                # Otra instancia y nuevas sesiones recuperan UUID y valores originales.
                another_repository = repository_class(self.sessions)
                self.assertCountEqual(await another_repository.list_all(), expected)

    async def test_failed_write_rolls_back_and_next_write_succeeds(self):
        for model, repository_class in REPOSITORIES:
            with self.subTest(repository=repository_class.__name__):
                repository = repository_class(self.sessions)
                original = model("Original")
                await repository.save(original)
                with self.assertRaises(IntegrityError):
                    await repository.save(model("Duplicado", id=original.id))
                following = model("Siguiente")
                await repository.save(following)
                self.assertCountEqual(await repository.list_all(), [original, following])
