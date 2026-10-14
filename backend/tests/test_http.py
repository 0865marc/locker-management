import unittest
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.http.routes import create_router
from application.use_cases import DeliveryService, ReturnService
from domain.models import Delivery, Return


class HttpAdapterTests(unittest.TestCase):
    def setUp(self):
        delivery = AsyncMock(spec=DeliveryService)
        returns = AsyncMock(spec=ReturnService)
        app = FastAPI()
        app.include_router(create_router(delivery, returns))
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.cases = (
            ("/deliveries", "address", Delivery("Calle Mayor 1"), delivery),
            ("/returns", "reason", Return("Producto dañado"), returns),
        )

    def test_create_and_list_delegate_to_services_and_serialize_entities(self):
        for path, field, entity, service in self.cases:
            with self.subTest(path=path):
                value = getattr(entity, field)
                expected = {"id": str(entity.id), field: value}
                service.create.return_value = entity
                service.list_all.return_value = [entity]

                response = self.client.post(path, json={field: value})
                self.assertEqual(response.status_code, 201)
                self.assertEqual(response.json(), expected)
                service.create.assert_awaited_once_with(value)

                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), [expected])
                service.list_all.assert_awaited_once_with()

    def test_business_validation_errors_become_http_422(self):
        for path, field, _, service in self.cases:
            with self.subTest(path=path):
                service.create.side_effect = ValueError("El valor no puede estar vacío")

                response = self.client.post(path, json={field: " "})

                self.assertEqual(response.status_code, 422)
                self.assertEqual(
                    response.json(), {"detail": "El valor no puede estar vacío"}
                )
                service.create.assert_awaited_once_with(" ")

    def test_invalid_request_bodies_do_not_call_services(self):
        for path, field, _, service in self.cases:
            for body in ({}, {field: None}, {field: []}):
                with self.subTest(path=path, body=body):
                    response = self.client.post(path, json=body)

                    self.assertEqual(response.status_code, 422)
                    service.create.assert_not_awaited()
                    service.list_all.assert_not_awaited()
