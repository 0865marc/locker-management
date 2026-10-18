"""Browser access policy through the real composition and HTTP middleware."""

import os
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from application.lockers.ports import LockerRepository
from application.quotations.ports import QuotationRepository


class CorsTests(unittest.TestCase):
    def make_app(self, origins: str | None) -> FastAPI:
        from main import create_app

        repository = AsyncMock(spec=LockerRepository)
        repository.list_all.return_value = []
        self.quotation_repository = AsyncMock(spec=QuotationRepository)
        self.publisher = AsyncMock()
        with (
            patch.dict("os.environ", {}, clear=False),
            patch("main.create_database", return_value=(AsyncMock(), object())),
            patch("main.SqlModelLockerRepository", return_value=repository),
            patch(
                "main.SqlModelQuotationRepository",
                return_value=self.quotation_repository,
            ),
        ):
            if origins is None:
                os.environ.pop("CORS_ALLOWED_ORIGINS", None)
            else:
                os.environ["CORS_ALLOWED_ORIGINS"] = origins
            return create_app(
                "postgresql+asyncpg://unused/unused", publisher=self.publisher
            )

    def test_json_preflight_is_uniform_across_paths(self) -> None:
        allowed = "https://project.pages.dev"
        with TestClient(self.make_app(allowed)) as client:
            for path, origin, method, headers, status in (
                ("/quotations", allowed, "POST", "content-type", 200),
                ("/quotations", allowed, "GET", "", 200),
                ("/quotations/", allowed, "POST", "content-type", 200),
                (
                    "/quotations/00000000-0000-4000-8000-000000000001",
                    allowed,
                    "POST",
                    "content-type",
                    200,
                ),
                ("/lockers", allowed, "POST", "content-type", 200),
                ("/deliveries", allowed, "POST", "content-type", 200),
                ("/returns", allowed, "POST", "content-type", 200),
                ("/missing", allowed, "GET", "content-type", 200),
                ("/missing", allowed, "POST", "content-type", 200),
                ("/quotations", allowed, "PATCH", "content-type", 400),
                ("/quotations", allowed, "DELETE", "content-type", 400),
                ("/quotations", allowed, "POST", "content-type,x-admin", 400),
                ("/quotations", allowed, "POST", "authorization", 400),
                ("/quotations", "https://other.pages.dev", "POST", "content-type", 400),
            ):
                with self.subTest(
                    path=path, origin=origin, method=method, headers=headers
                ):
                    preflight_headers = {
                        "Origin": origin,
                        "Access-Control-Request-Method": method,
                    }
                    if headers:
                        preflight_headers["Access-Control-Request-Headers"] = headers
                    response = client.options(path, headers=preflight_headers)
                    self.assertEqual(response.status_code, status)
                    self.assertNotIn(
                        "access-control-allow-credentials", response.headers
                    )
                    if origin != allowed:
                        self.assertNotIn(
                            "access-control-allow-origin", response.headers
                        )
                    if status == 200:
                        self.assertEqual(
                            response.headers["access-control-allow-origin"], allowed
                        )
                        self.assertIn(
                            "content-type",
                            response.headers["access-control-allow-headers"].lower(),
                        )
            for method in ("GET", "POST"):
                response = client.request(
                    method, "/missing", headers={"Origin": allowed}
                )
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json(), {"detail": "Not Found"})
                self.assertEqual(
                    response.headers["access-control-allow-origin"], allowed
                )
            self.quotation_repository.save.assert_not_awaited()
            self.publisher.publish.assert_not_awaited()

    def test_quotation_post_and_get_keep_real_contract_with_and_without_origin(
        self,
    ) -> None:
        allowed = "https://project.pages.dev"
        payload = {
            "origin_country_code": "ES",
            "origin_postal_code": "28001",
            "destination_country_code": "ES",
            "destination_postal_code": "01001",
            "weight_grams": 2500,
            "dimensions": {"width_mm": 150, "height_mm": 100, "depth_mm": 255},
        }
        for origin in (allowed, None):
            with (
                self.subTest(origin=origin),
                TestClient(self.make_app(allowed)) as client,
            ):
                headers = {"Origin": origin} if origin is not None else {}
                response = client.post("/quotations", json=payload, headers=headers)
                self.assertEqual(response.status_code, 202)
                self.assertEqual(response.json()["status"], "PENDING")
                saved = self.quotation_repository.save.call_args.args[0]
                self.publisher.publish.assert_awaited_once_with(saved.id)
                self.assertEqual(str(saved.id), response.json()["id"])
                self.quotation_repository.get.return_value = saved
                read = client.get(f"/quotations/{saved.id}", headers=headers)
                self.assertEqual(read.status_code, 200)
                self.assertEqual(read.json()["request"], payload)
                for result in (response, read):
                    self.assertNotIn("access-control-allow-credentials", result.headers)
                    if origin is None:
                        self.assertNotIn("access-control-allow-origin", result.headers)
                    else:
                        self.assertEqual(
                            result.headers["access-control-allow-origin"], allowed
                        )

    def test_quotation_validation_errors_remain_readable_for_allowed_origin(
        self,
    ) -> None:
        origin = "https://project.pages.dev"
        with TestClient(self.make_app(origin)) as client:
            response = client.post("/quotations", json={}, headers={"Origin": origin})
            self.assertEqual(response.status_code, 422)
            self.assertEqual(response.headers["access-control-allow-origin"], origin)
            self.quotation_repository.save.assert_not_awaited()
            self.publisher.publish.assert_not_awaited()

    def test_exact_allowed_origins_receive_readable_get_without_credentials(
        self,
    ) -> None:
        origins = ("http://localhost:4321", "https://lockers.example.org")
        with TestClient(self.make_app(f" {origins[0]}, {origins[1]} ")) as client:
            for origin in origins:
                with self.subTest(origin=origin):
                    response = client.get("/lockers", headers={"Origin": origin})
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json(), [])
                    self.assertEqual(
                        response.headers["access-control-allow-origin"], origin
                    )
                    self.assertNotIn(
                        "access-control-allow-credentials", response.headers
                    )
                    self.assertIn("Origin", response.headers["vary"])

    def test_unlisted_and_similar_origins_do_not_receive_access(self) -> None:
        with TestClient(self.make_app("https://project.pages.dev")) as client:
            for origin in (
                "https://other.pages.dev",
                "https://preview.project.pages.dev",
                "http://project.pages.dev",
                "https://project.pages.dev:8443",
                "null",
            ):
                with self.subTest(origin=origin):
                    response = client.get("/lockers", headers={"Origin": origin})
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.json(), [])
                    self.assertNotIn("access-control-allow-origin", response.headers)

    def test_preflight_grants_get_and_post_to_allowed_origin(self) -> None:
        allowed = "http://localhost:4321"
        with TestClient(self.make_app(allowed)) as client:
            for origin, method, status in (
                (allowed, "GET", 200),
                ("http://localhost:4322", "GET", 400),
                (allowed, "POST", 200),
                (allowed, "PATCH", 400),
                (allowed, "DELETE", 400),
            ):
                with self.subTest(origin=origin, method=method):
                    response = client.options(
                        "/lockers",
                        headers={
                            "Origin": origin,
                            "Access-Control-Request-Method": method,
                            "Access-Control-Request-Headers": "content-type",
                        },
                    )
                    self.assertEqual(response.status_code, status)
                    self.assertEqual(
                        response.headers["access-control-allow-methods"], "GET, POST"
                    )
                    self.assertNotIn(
                        "access-control-allow-credentials", response.headers
                    )
                    if origin != allowed:
                        self.assertNotIn(
                            "access-control-allow-origin", response.headers
                        )

    def test_missing_and_empty_configuration_allow_no_browser_origin(self) -> None:
        for value in (None, "", "   "):
            with self.subTest(value=value), TestClient(self.make_app(value)) as client:
                headers = {"Origin": "http://localhost:4321"}
                response = client.get("/lockers", headers=headers)
                self.assertEqual(response.status_code, 200)
                self.assertNotIn("access-control-allow-origin", response.headers)
                response = client.options(
                    "/lockers",
                    headers={**headers, "Access-Control-Request-Method": "GET"},
                )
                self.assertEqual(response.status_code, 400)
                quotation = client.options(
                    "/quotations",
                    headers={
                        **headers,
                        "Access-Control-Request-Method": "POST",
                        "Access-Control-Request-Headers": "content-type",
                    },
                )
                self.assertEqual(quotation.status_code, 400)

    def test_invalid_configuration_fails_before_allocating_infrastructure(self) -> None:
        invalid = (
            "*",
            "https://*.pages.dev",
            "null",
            "file://localhost",
            "localhost:4321",
            "https://",
            "https://user:password@example.org",
            "https://example.org/",
            "https://example.org/path",
            "https://example.org?x=1",
            "https://example.org?",
            "https://example.org#fragment",
            "https://example.org#",
            "https://exa mple.org",
            "https://example.org:abc",
            "https://example.org:65536",
            "https://example.org:",
            "https://example.org,",
            "https://example.org,,https://other.org",
            "https://example.org\n.evil.org",
            "http://[not-ipv6]",
            "http://[::1]extra",
            "https://example.org\\evil",
            "https://-example.org",
        )
        for value in invalid:
            from main import create_app

            with (
                self.subTest(value=value),
                patch.dict("os.environ", {"CORS_ALLOWED_ORIGINS": value}),
                patch("main.create_database") as database,
            ):
                with self.assertRaisesRegex(ValueError, "CORS_ALLOWED_ORIGINS"):
                    create_app(
                        "postgresql+asyncpg://unused/unused", publisher=AsyncMock()
                    )
                database.assert_not_called()

    def test_without_origin_routes_keep_their_status_and_representation(self) -> None:
        with TestClient(self.make_app("https://project.pages.dev")) as client:
            response = client.get("/lockers")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), [])
            self.assertNotIn("access-control-allow-origin", response.headers)
            self.assertEqual(client.get("/openapi.json").status_code, 200)
            self.assertEqual(client.get("/missing").status_code, 404)
            # CORS does not reject direct writes or change endpoint validation.
            self.assertEqual(client.post("/lockers", json={}).status_code, 422)

    def test_explicit_ipv6_origin_is_supported(self) -> None:
        origin = "http://[::1]:4321"
        with TestClient(self.make_app(origin)) as client:
            response = client.get("/lockers", headers={"Origin": origin})
            self.assertEqual(response.headers["access-control-allow-origin"], origin)
