"""Browser access policy through the real composition and HTTP middleware."""

import os
import unittest
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from application.lockers.ports import LockerRepository


class CorsTests(unittest.TestCase):
    def make_app(self, origins: str | None) -> FastAPI:
        from main import create_app

        repository = AsyncMock(spec=LockerRepository)
        repository.list_all.return_value = []
        with (
            patch.dict("os.environ", {}, clear=False),
            patch("main.create_database", return_value=(AsyncMock(), object())),
            patch("main.SqlModelLockerRepository", return_value=repository),
        ):
            if origins is None:
                os.environ.pop("CORS_ALLOWED_ORIGINS", None)
            else:
                os.environ["CORS_ALLOWED_ORIGINS"] = origins
            return create_app(
                "postgresql+asyncpg://unused/unused", publisher=AsyncMock()
            )

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

    def test_preflight_only_grants_get_to_allowed_origin(self) -> None:
        allowed = "http://localhost:4321"
        with TestClient(self.make_app(allowed)) as client:
            for origin, method, status in (
                (allowed, "GET", 200),
                ("http://localhost:4322", "GET", 400),
                (allowed, "POST", 400),
                (allowed, "PATCH", 400),
                (allowed, "DELETE", 400),
            ):
                with self.subTest(origin=origin, method=method):
                    response = client.options(
                        "/lockers",
                        headers={
                            "Origin": origin,
                            "Access-Control-Request-Method": method,
                        },
                    )
                    self.assertEqual(response.status_code, status)
                    self.assertEqual(
                        response.headers["access-control-allow-methods"], "GET"
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
