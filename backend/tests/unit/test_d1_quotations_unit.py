"""Fault boundaries and constant statement budget, without a SQL substitute."""

import unittest
from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import uuid4

from adapters.database.d1.bindings import D1BindingError, D1PreparedStatement, D1Value
from adapters.database.d1.quotations import D1QuotationRepository
from application.quotations.errors import QuotationStorageError
from application.quotations.models import ProviderResult, ProviderStatus


class Statement:
    def __init__(self, database: "Database", sql: str) -> None:
        self.database = database
        self.sql = sql
        self.values: tuple[D1Value, ...] = ()

    def bind(self, *values: D1Value) -> "Statement":
        self.values = values
        return self

    async def all(self) -> object:
        self.database.executions += 1
        raise D1BindingError("private SQL transport error")

    async def first(self) -> object:
        return await self.all()

    async def run(self) -> object:
        return await self.all()


class Database:
    def __init__(self, failure: bool = False, changes: int = 1) -> None:
        self.failure = failure
        self.changes = changes
        self.statements: list[Statement] = []
        self.executions = 0

    def prepare(self, sql: str) -> Statement:
        statement = Statement(self, sql)
        self.statements.append(statement)
        return statement

    async def batch(self, statements: Sequence[D1PreparedStatement]) -> object:
        self.executions += 1
        if self.failure:
            raise D1BindingError("private batch failure")
        return [
            {"success": True, "results": [], "meta": {"changes": self.changes}}
            for _ in statements
        ]


class QuotationFaultTests(unittest.IsolatedAsyncioTestCase):
    async def test_transport_failure_is_sanitized_without_retry(self):
        db = Database()
        repository = D1QuotationRepository(lambda: db)
        for operation in (repository.get, repository.start):
            db.executions = 0
            with self.assertRaises(QuotationStorageError) as raised:
                await operation(uuid4())
            self.assertNotIn("private", str(raised.exception))
            self.assertEqual(db.executions, 1)

    async def test_complete_uses_three_statements_and_one_batch(self):
        db = Database()
        repository = D1QuotationRepository(lambda: db)
        await repository.complete(
            uuid4(),
            tuple(
                ProviderResult(f"provider-{i}", ProviderStatus.NOT_COVERED)
                for i in range(300)
            ),
            datetime.now(timezone.utc),
        )
        self.assertEqual(db.executions, 1)
        self.assertEqual(len(db.statements), 3)
        self.assertTrue(all(len(statement.values) <= 3 for statement in db.statements))

    async def test_complete_batch_failure_is_not_retried(self):
        db = Database(failure=True)
        repository = D1QuotationRepository(lambda: db)
        with self.assertRaises(QuotationStorageError):
            await repository.complete(uuid4(), (), datetime.now(timezone.utc))
        self.assertEqual(db.executions, 1)

    async def test_complete_zero_transition_is_rejected(self):
        db = Database(changes=0)
        with self.assertRaisesRegex(QuotationStorageError, "not processing"):
            await D1QuotationRepository(lambda: db).complete(
                uuid4(), (), datetime.now(timezone.utc)
            )
        self.assertEqual(db.executions, 1)
