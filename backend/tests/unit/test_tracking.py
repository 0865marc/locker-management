"""Targeted tracking projections and real HTTP composition without services."""

import unittest
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch
from uuid import uuid4

from fastapi.testclient import TestClient

from application.deliveries.ports import DeliveryRepository
from application.lockers.ports import LockerRepository
from application.quotations.ports import QuotationRepository
from application.returns.ports import ReturnRepository
from application.tracking.use_cases import (
    TrackingConflictError,
    TrackingNotFoundError,
    TrackingService,
)
from domain.deliveries import Delivery
from domain.lockers import Address, Compartment, Coordinates, Dimensions, Locker
from domain.returns import Return

NOW = datetime(2026, 10, 18, tzinfo=timezone.utc)


class TrackingTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.deliveries = AsyncMock(spec=DeliveryRepository)
        self.returns = AsyncMock(spec=ReturnRepository)
        self.lockers = AsyncMock(spec=LockerRepository)
        self.deliveries.get_by_id.return_value = None
        self.returns.get_by_id.return_value = None
        self.service = TrackingService(self.deliveries, self.returns, self.lockers)
        self.identifier, self.locker_id = uuid4(), uuid4()
        self.delivery = Delivery(
            "private-tracking",
            "private-carrier",
            "private-name",
            NOW,
            recipient_phone="private-phone",
            id=self.identifier,
            pickup_deadline_at=NOW - timedelta(days=1),
            locker_id=self.locker_id,
            compartment_id=uuid4(),
            parcel_dimensions=Dimensions(100, 100, 100),
        )
        self.returned = Return(
            "private-tracking",
            "private-carrier",
            NOW,
            sender_name="private-name",
            id=self.identifier,
            locker_id=self.locker_id,
            compartment_id=uuid4(),
            parcel_dimensions=Dimensions(100, 100, 100),
        )
        self.locker = Locker(
            "Full inactive",
            active=False,
            id=self.locker_id,
            address=Address("ES", "01001", "Álava", "Vitoria", "Calle", "1"),
            coordinates=Coordinates(42.85, -2.67),
            compartments=(
                Compartment(self.locker_id, Dimensions(100, 100, 100), occupied=True),
            ),
        )
        self.lockers.get_by_id.return_value = self.locker

    def assert_targeted_reads(self, assigned: bool) -> None:
        self.assertEqual(
            [call[0] for call in self.deliveries.mock_calls], ["get_by_id"]
        )
        self.assertEqual([call[0] for call in self.returns.mock_calls], ["get_by_id"])
        self.assertEqual(
            [call[0] for call in self.lockers.mock_calls],
            ["get_by_id"] if assigned else [],
        )
        self.deliveries.get_by_id.assert_awaited_once_with(self.identifier)
        self.returns.get_by_id.assert_awaited_once_with(self.identifier)

    async def test_all_five_states_keep_assignment_without_availability_filter(
        self,
    ) -> None:
        for parcel, kind, relation in (
            (self.delivery, "delivery", "current"),
            (self.delivery.collect(NOW), "delivery", "last_known"),
            (self.delivery.return_to_carrier(NOW), "delivery", "last_known"),
            (self.returned, "return", "current"),
            (self.returned.hand_over(NOW), "return", "last_known"),
        ):
            with self.subTest(status=parcel.status):
                for repository in (self.deliveries, self.returns, self.lockers):
                    repository.reset_mock()
                self.deliveries.get_by_id.return_value = (
                    parcel if kind == "delivery" else None
                )
                self.returns.get_by_id.return_value = (
                    parcel if kind == "return" else None
                )
                result = await self.service.get_by_id(self.identifier)
                self.assertEqual(
                    (result.kind, result.status, result.locker_relation),
                    (kind, parcel.status, relation),
                )
                self.assertEqual(result.locker_id, self.locker_id)
                self.assertIsNotNone(result.locker)
                if result.locker is not None:
                    self.assertEqual(result.locker.location_id, "Full inactive")
                    self.assertEqual(result.locker.address, self.locker.address)
                    self.assertEqual(result.locker.coordinates, self.locker.coordinates)
                    self.assertEqual(
                        set(asdict(result.locker)),
                        {"location_id", "address", "coordinates"},
                    )
                self.assertEqual(
                    set(asdict(result)),
                    {"id", "kind", "status", "locker_relation", "locker_id", "locker"},
                )
                self.assertNotIn("private-", str(asdict(result)))
                self.assert_targeted_reads(True)

    async def test_unassigned_parcels_never_read_locker(self) -> None:
        for parcel, kind in (
            (self.delivery, "delivery"),
            (self.returned.hand_over(NOW), "return"),
        ):
            with self.subTest(kind=kind):
                for repository in (self.deliveries, self.returns, self.lockers):
                    repository.reset_mock()
                unassigned = replace(
                    parcel, locker_id=None, compartment_id=None, parcel_dimensions=None
                )
                self.deliveries.get_by_id.return_value = (
                    unassigned if kind == "delivery" else None
                )
                self.returns.get_by_id.return_value = (
                    unassigned if kind == "return" else None
                )
                result = await self.service.get_by_id(self.identifier)
                self.assertEqual(result.locker_relation, "unassigned")
                self.assertIsNone(result.locker_id)
                self.assertIsNone(result.locker)
                self.assert_targeted_reads(False)

    async def test_missing_metadata_keeps_assignment_and_custody_relation(self) -> None:
        self.deliveries.get_by_id.return_value = self.delivery.collect(NOW)
        self.lockers.get_by_id.return_value = None
        result = await self.service.get_by_id(self.identifier)
        self.assertEqual(result.locker_relation, "last_known")
        self.assertEqual(result.locker_id, self.locker_id)
        self.assertIsNone(result.locker)
        self.assert_targeted_reads(True)

    async def test_null_alias_address_and_coordinates_are_not_inferred(self) -> None:
        self.returns.get_by_id.return_value = self.returned
        self.lockers.get_by_id.return_value = Locker(id=self.locker_id)
        result = await self.service.get_by_id(self.identifier)
        self.assertIsNotNone(result.locker)
        if result.locker is not None:
            self.assertEqual(
                asdict(result.locker),
                {"location_id": None, "address": None, "coordinates": None},
            )

    async def test_no_match_and_collision_are_distinct_without_locker_reads(
        self,
    ) -> None:
        with self.assertRaises(TrackingNotFoundError):
            await self.service.get_by_id(self.identifier)
        self.assert_targeted_reads(False)
        self.deliveries.get_by_id.return_value = self.delivery
        self.returns.get_by_id.return_value = self.returned
        self.lockers.get_by_id.reset_mock()
        with self.assertRaises(TrackingConflictError):
            await self.service.get_by_id(self.identifier)
        self.lockers.get_by_id.assert_not_awaited()

    async def test_infrastructure_failure_never_becomes_not_found(self) -> None:
        for repository in (self.deliveries, self.returns, self.lockers):
            with self.subTest(repository=repository):
                self.deliveries.get_by_id.return_value = self.delivery
                repository.get_by_id.side_effect = ConnectionError("unavailable")
                with self.assertRaises(ConnectionError):
                    await self.service.get_by_id(self.identifier)
                repository.get_by_id.side_effect = None


class TrackingHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        from main import create_app

        self.deliveries = AsyncMock(spec=DeliveryRepository)
        self.returns = AsyncMock(spec=ReturnRepository)
        self.lockers = AsyncMock(spec=LockerRepository)
        self.quotations = AsyncMock(spec=QuotationRepository)
        self.deliveries.get_by_id.return_value = None
        self.returns.get_by_id.return_value = None
        self.locker_id, self.identifier = uuid4(), uuid4()
        self.delivery = Delivery(
            "hidden-tracking",
            "hidden-carrier",
            "hidden-name",
            NOW,
            recipient_phone="hidden-phone",
            id=self.identifier,
            locker_id=self.locker_id,
            compartment_id=uuid4(),
            parcel_dimensions=Dimensions(10, 10, 10),
        )
        self.lockers.get_by_id.return_value = Locker(
            "Locker", id=self.locker_id, active=False, coordinates=Coordinates(40, -3)
        )
        with (
            patch.dict("os.environ", {"CORS_ALLOWED_ORIGINS": "http://localhost:4321"}),
            patch("main.create_database", return_value=(AsyncMock(), object())),
            patch("main.SqlModelDeliveryRepository", return_value=self.deliveries),
            patch("main.SqlModelReturnRepository", return_value=self.returns),
            patch("main.SqlModelLockerRepository", return_value=self.lockers),
            patch("main.SqlModelQuotationRepository", return_value=self.quotations),
        ):
            self.app = create_app(
                "postgresql+asyncpg://unused/unused", publisher=AsyncMock()
            )
        self.client = TestClient(self.app, raise_server_exceptions=False)
        self.addCleanup(self.client.close)

    def test_minimal_json_and_existing_get_cors_with_shared_repositories(self) -> None:
        self.deliveries.get_by_id.return_value = self.delivery
        response = self.client.get(
            f"/tracking/{self.identifier}", headers={"Origin": "http://localhost:4321"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "id": str(self.identifier),
                "kind": "delivery",
                "status": "AWAITING_PICKUP",
                "locker_relation": "current",
                "locker_id": str(self.locker_id),
                "locker": {
                    "location_id": "Locker",
                    "address": None,
                    "coordinates": {"latitude": 40.0, "longitude": -3.0},
                },
            },
        )
        self.assertEqual(
            response.headers["access-control-allow-origin"], "http://localhost:4321"
        )
        self.assertNotIn("access-control-allow-credentials", response.headers)
        self.assertIs(
            self.app.state.tracking_service.deliveries,
            self.app.state.delivery_service.repository,
        )
        self.assertIs(
            self.app.state.tracking_service.returns,
            self.app.state.return_service.repository,
        )
        self.assertIs(
            self.app.state.tracking_service.lockers,
            self.app.state.locker_service.repository,
        )
        self.deliveries.list_all.assert_not_awaited()
        self.returns.list_all.assert_not_awaited()
        self.lockers.list_all.assert_not_awaited()
        self.quotations.get.assert_not_awaited()

    def test_404_422_409_and_infrastructure_500_remain_distinct(self) -> None:
        self.assertEqual(
            self.client.get(f"/tracking/{self.identifier}").status_code, 404
        )
        self.deliveries.reset_mock()
        self.returns.reset_mock()
        self.assertEqual(self.client.get("/tracking/not-a-uuid").status_code, 422)
        self.deliveries.get_by_id.assert_not_awaited()
        self.returns.get_by_id.assert_not_awaited()
        self.deliveries.get_by_id.return_value = self.delivery
        self.returns.get_by_id.return_value = Return(
            "hidden", "hidden", NOW, id=self.identifier
        )
        self.assertEqual(
            self.client.get(f"/tracking/{self.identifier}").status_code, 409
        )
        self.lockers.get_by_id.assert_not_awaited()
        self.returns.get_by_id.return_value = None
        self.deliveries.get_by_id.side_effect = ConnectionError("unavailable")
        self.assertEqual(
            self.client.get(f"/tracking/{self.identifier}").status_code, 500
        )

    def test_new_route_is_read_only(self) -> None:
        self.assertEqual(
            self.client.post(f"/tracking/{self.identifier}", json={}).status_code, 405
        )
        self.deliveries.get_by_id.assert_not_awaited()
        self.returns.get_by_id.assert_not_awaited()
