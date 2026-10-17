"""Unit fault checks complement, and do not replace, native D1 contracts."""

import unittest
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi.testclient import TestClient

from adapters.database.d1.bindings import D1BindingError, D1PreparedStatement, D1Value
from adapters.database.d1.core import (
    batch,
    identifier,
    instant,
    integer,
    result,
    statement,
    timestamp,
)
from adapters.database.d1.lockers import D1LockerRepository
from application.deliveries.ports import DeliveryRepository
from application.persistence import PersistenceError
from application.quotations.ports import QuotationPublisher, QuotationRepository
from application.returns.ports import ReturnRepository
from composition import create_application


class FailingDatabase:
    def __init__(self) -> None:
        self.calls = 0

    def prepare(self, sql: str) -> D1PreparedStatement:
        raise AssertionError(sql)

    async def batch(self, statements: Sequence[D1PreparedStatement]) -> object:
        self.calls += 1
        raise D1BindingError("secret SQL token credentials")


class FaultStatement:
    def bind(self, *values: D1Value) -> D1PreparedStatement:
        raise D1BindingError("secret SQL bind token")

    async def first(self) -> object:
        raise AssertionError("not reached")

    async def all(self) -> object:
        raise AssertionError("not reached")

    async def run(self) -> object:
        raise AssertionError("not reached")


class PrepareFaultDatabase(FailingDatabase):
    def __init__(self, at_bind: bool = False) -> None:
        super().__init__()
        self.at_bind = at_bind

    def prepare(self, sql: str) -> D1PreparedStatement:
        if self.at_bind:
            return FaultStatement()
        raise D1BindingError("secret SQL prepare token")


class CoreTests(unittest.IsolatedAsyncioTestCase):
    def test_precise_canonical_values(self) -> None:
        value = datetime(
            2026, 1, 2, 3, 4, 5, 123456, tzinfo=timezone(timedelta(hours=3))
        )
        encoded = timestamp(value)
        self.assertEqual(encoded, "2026-01-02T00:04:05.123456Z")
        self.assertEqual(instant({"at": encoded}, "at"), value)
        key = uuid4()
        self.assertEqual(identifier({"id": str(key)}, "id"), key)
        for bad in (str(key).upper(), key.hex):
            with self.assertRaises(ValueError):
                identifier({"id": bad}, "id")
        for bad in (1.0, True, "1"):
            with self.assertRaises(ValueError):
                integer({"n": bad}, "n")
        for bad in ("2026-01-02T00:04:05Z", "2026-01-02T00:04:05.123456+00:00"):
            with self.assertRaises(ValueError):
                instant({"at": bad}, "at")

    def test_native_shape_validated(self) -> None:
        parsed = result(
            {"success": True, "meta": {"changes": 1}, "results": [{"n": 2147483647}]}
        )
        self.assertEqual(parsed.changes, 1)
        self.assertEqual(integer(parsed.results[0], "n"), 2147483647)
        for value in (
            {"success": False},
            {"success": True, "meta": {"changes": 1.0}},
            {"success": True, "meta": {"changes": 0}, "results": [{"x": True}]},
        ):
            with self.assertRaises(PersistenceError):
                result(value)

    async def test_unknown_commit_never_retried_and_message_sanitized(self) -> None:
        database = FailingDatabase()
        with self.assertRaises(PersistenceError) as failure:
            await batch(database, [])
        self.assertEqual(database.calls, 1)
        self.assertEqual(
            str(failure.exception), "Persistence is temporarily unavailable"
        )

    def test_prepare_and_bind_failures_are_sanitized_http_503(self) -> None:
        for at_bind in (False, True):
            database = PrepareFaultDatabase(at_bind)
            with self.assertRaises(PersistenceError):
                statement(database, "SELECT ?", 1)
            app = create_application(
                AsyncMock(spec=DeliveryRepository),
                AsyncMock(spec=ReturnRepository),
                D1LockerRepository(lambda: database),
                AsyncMock(spec=QuotationRepository),
                AsyncMock(spec=QuotationPublisher),
            )
            with TestClient(app) as client:
                response = client.post(
                    "/lockers",
                    json={
                        "location_id": "location",
                        "compartments": [
                            {
                                "quantity": 1,
                                "dimensions": {
                                    "width_mm": 1,
                                    "height_mm": 2,
                                    "depth_mm": 3,
                                },
                            }
                        ],
                    },
                )
            self.assertEqual(response.status_code, 503, response.text)
            self.assertEqual(response.json(), {"detail": "Persistence unavailable"})
            self.assertEqual(database.calls, 0)
