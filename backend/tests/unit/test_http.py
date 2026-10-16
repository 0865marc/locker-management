import unittest
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from httpx import Response

from fastapi import FastAPI
from fastapi.testclient import TestClient

from adapters.http.routes import create_router
from application.lockers import LockerService
from application.deliveries import DeliveryService, DeliveryNotFoundError
from application.returns import ReturnService, ReturnNotFoundError
from domain.deliveries import Delivery, DeliveryConflictError
from domain.returns import Return, ReturnConflictError


class HttpAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.delivery = AsyncMock(spec=DeliveryService)
        self.returns = AsyncMock(spec=ReturnService)
        app = FastAPI()
        app.include_router(create_router(self.delivery, self.returns, AsyncMock(spec=LockerService)))
        self.client = TestClient(app)
        self.addCleanup(self.client.close)
        self.at = datetime(2026, 10, 14, 10, tzinfo=timezone.utc)
        self.delivery_entity = Delivery("PKG-42", "carrier-a", "Ana García", self.at)
        self.return_entity = Return("RET-42", "carrier-a", self.at)
        self.cases = (
            ("/deliveries", {"tracking_number": "PKG-42", "carrier_code": "carrier-a",
                             "recipient_name": "Ana García"}, self.delivery_entity, self.delivery),
            ("/returns", {"tracking_number": "RET-42", "carrier_code": "carrier-a"},
             self.return_entity, self.returns),
        )
        self.actions = (
            (f"/deliveries/{self.delivery_entity.id}/collect", self.delivery.collect,
             self.delivery_entity.collect(self.at), DeliveryNotFoundError, DeliveryConflictError),
            (f"/deliveries/{self.delivery_entity.id}/return-to-carrier", self.delivery.return_to_carrier,
             self.delivery_entity.return_to_carrier(self.at), DeliveryNotFoundError, DeliveryConflictError),
            (f"/returns/{self.return_entity.id}/hand-over", self.returns.hand_over,
             self.return_entity.hand_over(self.at), ReturnNotFoundError, ReturnConflictError),
        )

    def assert_entity(self, response: Response, entity: Delivery | Return) -> None:
        body = response.json()
        self.assertEqual(set(body), set(vars(entity)))
        for key, value in vars(entity).items():
            if isinstance(value, datetime):
                self.assertEqual(datetime.fromisoformat(body[key].replace("Z", "+00:00")), value)
                self.assertTrue(body[key].endswith(("Z", "+00:00")))
            elif key == "id":
                self.assertEqual(body[key], str(value))
            else:
                self.assertEqual(body[key], value)

    def test_create_and_list_serialize_complete_entities_with_nulls(self) -> None:
        for path, payload, entity, service in self.cases:
            with self.subTest(path=path):
                service.create.return_value = entity
                service.list_all.return_value = [entity]
                response = self.client.post(path, json=payload)
                self.assertEqual(response.status_code, 201)
                self.assert_entity(response, entity)
                expected = dict(payload, locker_id=None, parcel_dimensions=None)
                if path == "/deliveries":
                    expected.update(recipient_phone=None, pickup_deadline_at=None)
                else:
                    expected.update(sender_name=None)
                service.create.assert_awaited_once_with(**expected)
                listed = self.client.get(path)
                self.assertEqual(listed.status_code, 200)
                self.assertEqual(listed.json(), [response.json()])
                service.list_all.assert_awaited_once_with()
                service.list_all.return_value = []
                self.assertEqual(self.client.get(path).json(), [])

    def test_optional_data_deadline_and_documented_payloads(self) -> None:
        payload = {"tracking_number": "PKG-42", "carrier_code": "carrier-a",
                   "recipient_name": "Ana García", "recipient_phone": "600123456",
                   "pickup_deadline_at": "2026-10-20T18:00:00+02:00"}
        deadline = datetime.fromisoformat(payload["pickup_deadline_at"])
        entity = Delivery("PKG-42", "carrier-a", "Ana García", self.at,
                          recipient_phone="600123456", pickup_deadline_at=deadline)
        self.delivery.create.return_value = entity
        response = self.client.post("/deliveries", json=payload)
        self.assertEqual(response.status_code, 201)
        self.assert_entity(response, entity)
        self.assertEqual(response.json()["pickup_deadline_at"], "2026-10-20T16:00:00Z")
        self.delivery.create.assert_awaited_once_with(**(payload | {"pickup_deadline_at": deadline, "locker_id": None, "parcel_dimensions": None}))
        self.returns.create.return_value = Return("RET-42", "carrier-a", self.at, sender_name="Luis Pérez")
        response = self.client.post("/returns", json={"tracking_number": "RET-42", "carrier_code": "carrier-a", "sender_name": "Luis Pérez"})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["sender_name"], "Luis Pérez")

    def test_invalid_creation_types_missing_fields_and_deadlines_never_invoke_service(self) -> None:
        for path, payload, _, service in self.cases:
            bodies = [None, [], False, 0, "text", {}]
            for key in payload:
                bodies.append({k: v for k, v in payload.items() if k != key})
                bodies.extend(payload | {key: value} for value in (None, [], {}, 123, False))
            optional = "recipient_phone" if path == "/deliveries" else "sender_name"
            bodies.extend(payload | {optional: value} for value in ([], {}, 123, False))
            if path == "/deliveries":
                bodies.extend(payload | {"pickup_deadline_at": value} for value in
                              ("2026-10-14T10:00:00", "2026-10-14", "invalid", "0", "1760000000", 123, False, [], {}))
            for body in bodies:
                with self.subTest(path=path, body=body):
                    response = self.client.post(path, json=body)
                    self.assertEqual(response.status_code, 422)
                    service.create.assert_not_awaited()

    def test_unknown_legacy_and_system_fields_never_invoke_creation(self) -> None:
        common = ("id", "status", "received_at", "storage_location", "order_reference", "unknown")
        for path, payload, _, service in self.cases:
            fields = common + (("address", "delivery_instructions", "collected_at", "returned_to_carrier_at")
                               if path == "/deliveries" else
                               ("reason", "item_sku", "quantity", "requested_resolution", "sender_phone", "handed_over_at", "delivery_id"))
            for field in fields:
                with self.subTest(path=path, field=field):
                    self.assertEqual(self.client.post(path, json=payload | {field: None}).status_code, 422)
                    service.create.assert_not_awaited()

    def test_domain_validation_errors_become_http_422(self) -> None:
        for path, payload, _, service in self.cases:
            for key in payload:
                with self.subTest(path=path, key=key):
                    service.create.side_effect = ValueError("El texto no puede estar vacío")
                    response = self.client.post(path, json=payload | {key: " "})
                    self.assertEqual(response.status_code, 422)
                    self.assertEqual(response.json(), {"detail": "El texto no puede estar vacío"})

    def test_actions_delegate_uuid_and_return_complete_entity(self) -> None:
        for path, operation, entity, *_ in self.actions:
            operation.return_value = entity
            for options in ({}, {"json": {}}):
                with self.subTest(path=path, options=options):
                    operation.reset_mock()
                    response = self.client.post(path, **options)
                    self.assertEqual(response.status_code, 200)
                    self.assert_entity(response, entity)
                    operation.assert_awaited_once_with(entity.id)

    def test_invalid_action_bodies_and_identifiers_do_not_invoke_services(self) -> None:
        for path, operation, *_ in self.actions:
            for raw in ('null', '[]', 'false', '0', '"text"', '{"status":"COLLECTED"}', '{"id":null}', '{'):
                with self.subTest(path=path, raw=raw):
                    response = self.client.post(path, content=raw, headers={"Content-Type": "application/json"})
                    self.assertEqual(response.status_code, 422)
                    operation.assert_not_awaited()
            malformed = path.split("/")
            malformed[2] = "not-a-uuid"
            self.assertEqual(self.client.post("/".join(malformed)).status_code, 422)
            operation.assert_not_awaited()

    def test_not_found_and_conflicts_have_distinct_statuses(self) -> None:
        for path, operation, _, not_found_error, conflict_error in self.actions:
            for error, code in ((not_found_error("No existe"), 404),
                                (conflict_error("Ya ha salido o perdió la carrera"), 409),
                                (conflict_error("Fecha anterior a recepción"), 409)):
                with self.subTest(path=path, code=code):
                    operation.side_effect = error
                    response = self.client.post(path)
                    self.assertEqual(response.status_code, code)
                    self.assertEqual(response.json(), {"detail": str(error)})

    def test_infrastructure_failures_are_not_business_errors_or_successes(self) -> None:
        for path, payload, _, service in self.cases:
            service.create.side_effect = RuntimeError("Fallo de conexión")
            with self.assertRaisesRegex(RuntimeError, "Fallo de conexión"):
                self.client.post(path, json=payload)
        for path, operation, *_ in self.actions:
            operation.side_effect = RuntimeError("Fallo de commit")
            with self.assertRaisesRegex(RuntimeError, "Fallo de commit"):
                self.client.post(path)
