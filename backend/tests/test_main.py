"""Prueba HTTP + PostgreSQL previamente migrado, opcional y sin borrar registros."""

import os
import unittest
from uuid import uuid4


@unittest.skipUnless(os.getenv("TEST_DATABASE_URL"), "Requiere TEST_DATABASE_URL")
class HttpPostgresTests(unittest.TestCase):
    def test_create_list_and_persist_across_app_instances(self):
        from fastapi.testclient import TestClient

        from main import create_app

        database_url = os.environ["TEST_DATABASE_URL"]
        created = {}
        with TestClient(create_app(database_url)) as client:
            for path, field in (("/deliveries", "address"), ("/returns", "reason")):
                with self.subTest(path=path):
                    value = f"Prueba {uuid4()}"
                    response = client.post(path, json={field: f"  {value}  "})
                    self.assertEqual(response.status_code, 201)
                    self.assertEqual(response.json()[field], value)
                    self.assertIn("id", response.json())
                    created[path] = response.json()
                    for invalid in ({field: "   "}, {}, {field: 123}):
                        self.assertEqual(client.post(path, json=invalid).status_code, 422)

        # Una nueva aplicación y un nuevo pool leen los datos persistidos con SQLModel.
        with TestClient(create_app(database_url)) as client:
            for path, item in created.items():
                with self.subTest(path=path):
                    response = client.get(path)
                    self.assertEqual(response.status_code, 200)
                    self.assertIn(item, response.json())
