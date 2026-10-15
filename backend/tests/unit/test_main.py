"""Composition and startup with simulated infrastructure only."""

import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from application.use_cases import DeliveryService, ReturnService


class CompositionTests(unittest.TestCase):
    def test_services_are_composed_once_and_engine_is_disposed(self):
        from main import create_app

        engine = AsyncMock()
        sessions = object()
        with patch("main.create_database", return_value=(engine, sessions)), \
             patch("main.SqlModelDeliveryRepository") as delivery_repo, \
             patch("main.SqlModelReturnRepository") as return_repo, \
             patch("main.SqlModelLockerRepository") as locker_repo:
            app = create_app("postgresql+asyncpg://unused/unused")
        delivery_repo.assert_called_once_with(sessions)
        return_repo.assert_called_once_with(sessions)
        locker_repo.assert_called_once_with(sessions)
        from application.locker_use_cases import LockerService
        self.assertIsInstance(app.state.locker_service, LockerService)
        self.assertIsInstance(app.state.delivery_service, DeliveryService)
        self.assertIsInstance(app.state.return_service, ReturnService)
        with TestClient(app):
            engine.dispose.assert_not_awaited()
        engine.dispose.assert_awaited_once_with()

    def test_lifespan_does_not_create_or_migrate_tables(self):
        from main import create_app

        engine = AsyncMock()
        sessions = object()
        with patch("main.create_database", return_value=(engine, sessions)) as factory:
            app = create_app("postgresql+asyncpg://unused/unused")
        with TestClient(app) as client:
            self.assertEqual(client.get("/openapi.json").status_code, 200)
        factory.assert_called_once_with("postgresql+asyncpg://unused/unused")
        engine.connect.assert_not_called()
        engine.begin.assert_not_called()
        engine.dispose.assert_awaited_once_with()
