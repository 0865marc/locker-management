"""Shared composition preserves routes, clock injection and public errors."""

import subprocess
import sys
import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from application.deliveries.ports import DeliveryRepository
from application.lockers.ports import LockerRepository
from application.persistence import PersistenceError
from application.quotations.ports import QuotationPublisher, QuotationRepository
from application.returns.ports import ReturnRepository
from composition import create_application


class SharedCompositionTests(unittest.TestCase):
    def test_services_are_reused_and_clock_is_injected(self) -> None:
        deliveries = AsyncMock(spec=DeliveryRepository)
        moment = datetime(2026, 10, 17, 12, 0, tzinfo=timezone.utc)
        app = create_application(
            deliveries,
            AsyncMock(spec=ReturnRepository),
            AsyncMock(spec=LockerRepository),
            AsyncMock(spec=QuotationRepository),
            AsyncMock(spec=QuotationPublisher),
            clock=lambda: moment,
        )
        services = (
            app.state.delivery_service,
            app.state.return_service,
            app.state.locker_service,
            app.state.quotation_service,
        )
        with TestClient(app) as client:
            for _ in range(2):
                response = client.post(
                    "/deliveries",
                    json={
                        "tracking_number": "D",
                        "carrier_code": "C",
                        "recipient_name": "Ana",
                    },
                )
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.json()["received_at"], "2026-10-17T12:00:00Z")
            schema = client.get("/openapi.json").json()
            for path in ("/deliveries", "/returns", "/lockers", "/quotations"):
                self.assertIn(path, schema["paths"])
            self.assertEqual(schema["info"]["title"], "Locker Management Demo")
        self.assertEqual(
            services,
            (
                app.state.delivery_service,
                app.state.return_service,
                app.state.locker_service,
                app.state.quotation_service,
            ),
        )
        self.assertEqual(deliveries.save.await_count, 2)

    def test_persistence_error_is_sanitized_without_disguising_programming_errors(
        self,
    ) -> None:
        deliveries = AsyncMock(spec=DeliveryRepository)
        app = create_application(
            deliveries,
            AsyncMock(spec=ReturnRepository),
            AsyncMock(spec=LockerRepository),
            AsyncMock(spec=QuotationRepository),
            AsyncMock(spec=QuotationPublisher),
        )
        with TestClient(app) as client:
            failure = PersistenceError()
            failure.args = ("secret-token SELECT * FROM parcels",)
            deliveries.list_all.side_effect = failure
            response = client.get("/deliveries")
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json(), {"detail": "Persistence unavailable"})
            deliveries.list_all.side_effect = TypeError("programming error")
            with self.assertRaisesRegex(TypeError, "programming error"):
                client.get("/deliveries")

    def test_import_composition_does_not_import_infrastructure(self) -> None:
        script = """
import entrypoints, sys
assert not any(name.startswith("entrypoints.") for name in sys.modules)
assert "fastapi" not in sys.modules
import composition
for module in ('entrypoints.api', 'entrypoints.rabbitmq_consumer', 'workers', 'sqlmodel', 'asyncpg', 'aio_pika', 'alembic'):
    assert module not in sys.modules, module
"""
        result = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)
