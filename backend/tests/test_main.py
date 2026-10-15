"""Composición sin migraciones automáticas e integración PostgreSQL opcional."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import uuid4

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
            app = create_app("sqlite+aiosqlite://")
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

        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "unprepared.sqlite"
            with TestClient(create_app(f"sqlite+aiosqlite:///{database}")) as client:
                self.assertEqual(client.get("/openapi.json").status_code, 200)
            self.assertFalse(database.exists())


@unittest.skipUnless(os.getenv("TEST_DATABASE_URL"), "Requiere TEST_DATABASE_URL")
class HttpPostgresTests(unittest.TestCase):
    def test_create_exit_list_and_persist_across_app_instances(self):
        from main import create_app

        database_url = os.environ["TEST_DATABASE_URL"]
        created = {}
        cases = (
            ("/deliveries", {"tracking_number": f"PKG-{uuid4()}", "carrier_code": "carrier-a",
                             "recipient_name": "Ana García", "recipient_phone": " 600123456 ",
                             "pickup_deadline_at": "2020-01-01T12:00:00+02:00"}, "collect", "COLLECTED"),
            ("/deliveries", {"tracking_number": f"PKG-{uuid4()}", "carrier_code": "carrier-a",
                             "recipient_name": "Luis Pérez"}, "return-to-carrier", "RETURNED_TO_CARRIER"),
            ("/returns", {"tracking_number": f"RET-{uuid4()}", "carrier_code": "carrier-a",
                          "sender_name": " "}, "hand-over", "HANDED_OVER"),
        )
        with TestClient(create_app(database_url)) as client:
            for path, payload, action, status in cases:
                with self.subTest(path=path, action=action):
                    response = client.post(path, json=payload | {"tracking_number": f"  {payload['tracking_number']}  "})
                    self.assertEqual(response.status_code, 201, response.text)
                    item = response.json()
                    self.assertEqual(item["tracking_number"], payload["tracking_number"])
                    self.assertTrue(item["received_at"].endswith(("Z", "+00:00")))
                    if action == "collect":
                        self.assertEqual(item["recipient_phone"], "600123456")
                        self.assertEqual(item["pickup_deadline_at"], "2020-01-01T10:00:00Z")
                    if path == "/returns":
                        self.assertIsNone(item["sender_name"])
                    action_path = f"{path}/{item['id']}/{action}"
                    exited = client.post(action_path, json={})
                    self.assertEqual(exited.status_code, 200, exited.text)
                    self.assertEqual(exited.json()["status"], status)
                    created.setdefault(path, []).append(exited.json())
                    self.assertEqual(client.post(action_path).status_code, 409)
                    if action == "collect":
                        self.assertEqual(client.post(f"{path}/{item['id']}/return-to-carrier").status_code, 409)
                    for invalid in ({}, payload | {"tracking_number": "   "}, payload | {"tracking_number": 123}):
                        self.assertEqual(client.post(path, json=invalid).status_code, 422)

        # Una nueva aplicación/pool recupera identidad, campos, estado y fecha ganadora.
        with TestClient(create_app(database_url)) as client:
            for path, items in created.items():
                response = client.get(path)
                self.assertEqual(response.status_code, 200)
                for item in items:
                    self.assertIn(item, response.json())
            for path in (f"/deliveries/{uuid4()}/collect", f"/returns/{uuid4()}/hand-over"):
                self.assertEqual(client.post(path).status_code, 404)
