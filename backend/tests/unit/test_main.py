"""Composition and startup with simulated infrastructure only."""

import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from application.deliveries import DeliveryService
from application.returns import ReturnService
from domain.ports import DeliveryRepository, ReturnRepository, LockerRepository


class CompositionTests(unittest.TestCase):
    def test_services_are_composed_once_and_engine_is_disposed(self) -> None:
        from main import create_app

        engine = AsyncMock()
        sessions = object()
        with patch("main.create_database", return_value=(engine, sessions)), \
             patch("main.SqlModelDeliveryRepository") as delivery_repo, \
             patch("main.SqlModelReturnRepository") as return_repo, \
             patch("main.SqlModelLockerRepository") as locker_repo:
            app = create_app("postgresql+asyncpg://unused/unused", publisher=AsyncMock())
        delivery_repo.assert_called_once_with(sessions)
        return_repo.assert_called_once_with(sessions)
        locker_repo.assert_called_once_with(sessions)
        from application.lockers import LockerService
        self.assertIsInstance(app.state.locker_service, LockerService)
        self.assertIsInstance(app.state.delivery_service, DeliveryService)
        self.assertIsInstance(app.state.return_service, ReturnService)
        with TestClient(app):
            engine.dispose.assert_not_awaited()
        engine.dispose.assert_awaited_once_with()

    def test_lifespan_does_not_create_or_migrate_tables(self) -> None:
        from main import create_app

        engine = AsyncMock()
        sessions = object()
        with patch("main.create_database", return_value=(engine, sessions)) as factory:
            app = create_app("postgresql+asyncpg://unused/unused", publisher=AsyncMock())
        with TestClient(app) as client:
            self.assertEqual(client.get("/openapi.json").status_code, 200)
        factory.assert_called_once_with("postgresql+asyncpg://unused/unused")
        engine.connect.assert_not_called()
        engine.begin.assert_not_called()
        engine.dispose.assert_awaited_once_with()

    def test_composition_provides_real_utc_clock_for_both_receptions(self) -> None:
        from main import create_app

        engine = AsyncMock()
        delivery_repository = AsyncMock(spec=DeliveryRepository)
        return_repository = AsyncMock(spec=ReturnRepository)
        locker_repository = AsyncMock(spec=LockerRepository)
        with patch("main.create_database", return_value=(engine, object())), \
             patch("main.SqlModelDeliveryRepository", return_value=delivery_repository), \
             patch("main.SqlModelReturnRepository", return_value=return_repository), \
             patch("main.SqlModelLockerRepository", return_value=locker_repository):
            app = create_app("postgresql+asyncpg://unused/unused", publisher=AsyncMock())
        before = datetime.now(timezone.utc)
        with TestClient(app) as client:
            for path, payload in (
                ("/deliveries", {"tracking_number": "D", "carrier_code": "C", "recipient_name": "Ana"}),
                ("/returns", {"tracking_number": "R", "carrier_code": "C"}),
            ):
                with self.subTest(path=path):
                    response = client.post(path, json=payload)
                    self.assertEqual(response.status_code, 201)
                    received = datetime.fromisoformat(response.json()["received_at"].replace("Z", "+00:00"))
                    self.assertIs(received.tzinfo, timezone.utc)
                    self.assertLessEqual(before, received)
                    self.assertLessEqual(received, datetime.now(timezone.utc))
        delivery_repository.save.assert_awaited_once()
        return_repository.save.assert_awaited_once()
        engine.dispose.assert_awaited_once_with()

    def test_broker_lifecycle_and_cleanup_even_when_startup_fails(self) -> None:
        from main import create_app
        for failure in (None, ConnectionError('unavailable')):
            engine, broker = AsyncMock(), AsyncMock()
            broker.open.side_effect = failure
            with patch('main.create_database', return_value=(engine, object())), \
                 patch('main.RabbitMQ', return_value=broker):
                app = create_app('postgresql+asyncpg://unused/unused')
            if failure is None:
                with TestClient(app):
                    broker.open.assert_awaited_once()
                    broker.close.assert_not_awaited()
            else:
                with self.assertRaises(ConnectionError):
                    with TestClient(app):
                        pass
            broker.close.assert_awaited_once()
            engine.dispose.assert_awaited_once()
