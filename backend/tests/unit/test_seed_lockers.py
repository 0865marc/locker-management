"""Manual synthetic-data generation, geographic membership and HTTP outcomes."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from email.message import Message
from http.client import IncompleteRead
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError
from uuid import UUID

from adapters.http.lockers.schemas import CreateLocker
from scripts import seed_lockers as seed


class SeedGeometryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.polygons = seed.load_boundary()

    def test_thousand_available_payloads_are_deterministic_and_on_spanish_land(
        self,
    ) -> None:
        payloads = seed.generate_payloads(1000, 42, self.polygons)
        self.assertEqual(len(payloads), 1000)
        self.assertEqual(payloads, seed.generate_payloads(1000, 42, self.polygons))
        self.assertNotEqual(payloads[:3], seed.generate_payloads(3, 43, self.polygons))
        self.assertEqual(len(self.polygons), 23)
        self.assertEqual(len({item["location_id"] for item in payloads}), 1000)
        for index, payload in enumerate(payloads, start=1):
            coordinates = payload["coordinates"]
            point = (coordinates["longitude"], coordinates["latitude"])
            self.assertTrue(seed.on_land(point, self.polygons), point)
            # Validate every generated POST body against the unchanged API contract.
            parsed = CreateLocker.model_validate(payload)
            self.assertIs(parsed.active, True)
            self.assertIsNone(parsed.address)
            self.assertEqual(parsed.location_id, f"DEMO-42-{index}")
            self.assertEqual(len(parsed.compartments), 1)
            batch = parsed.compartments[0]
            self.assertEqual(batch.quantity, 6)
            self.assertIs(batch.enabled, True)
            self.assertEqual(
                batch.dimensions.model_dump(),
                {"width_mm": 400, "height_mm": 400, "depth_mm": 600},
            )
            self.assertNotIn("occupied", payload)

    def test_reference_land_and_sea_positions(self) -> None:
        for point in (
            (-3.7038, 40.4168),  # Madrid
            (2.65, 39.60),  # Mallorca
            (-16.31, 28.46),  # Tenerife
            (-5.35, 35.90),  # Ceuta
            (-2.95, 35.29),  # Melilla
            (1.981, 42.464),  # Llívia
        ):
            with self.subTest(point=point):
                self.assertTrue(seed.on_land(point, self.polygons))
        for point in ((-9.14, 38.72), (2.35, 48.86), (0.0, 38.0), (-12.0, 30.0)):
            with self.subTest(point=point):
                self.assertFalse(seed.on_land(point, self.polygons))

    def test_shell_holes_and_edges(self) -> None:
        shell = ((0.0, 0.0), (4.0, 0.0), (4.0, 4.0), (0.0, 4.0), (0.0, 0.0))
        hole = ((1.0, 1.0), (3.0, 1.0), (3.0, 3.0), (1.0, 3.0), (1.0, 1.0))
        polygon = seed.Polygon((shell, hole), (0.0, 0.0, 4.0, 4.0))
        self.assertTrue(seed.on_land((0.5, 0.5), (polygon,)))
        for point in ((2.0, 2.0), (1.0, 2.0), (0.0, 2.0), (4.1, 2.0)):
            self.assertFalse(seed.on_land(point, (polygon,)))
        generated = seed.generate_payloads(100, 42, (polygon,))
        for payload in generated:
            point = payload["coordinates"]
            self.assertFalse(
                1 <= point["longitude"] <= 3 and 1 <= point["latitude"] <= 3
            )

    def test_rounding_is_checked_again_before_emitting_coordinates(self) -> None:
        shell = (
            (0.0000004, 0.0),
            (1.0, 0.0),
            (1.0, 1.0),
            (0.0000004, 1.0),
            (0.0000004, 0.0),
        )
        polygon = seed.Polygon((shell,), (0.0000004, 0.0, 1.0, 1.0))
        with patch("scripts.seed_lockers.random.Random") as random:
            random.return_value.uniform.side_effect = [0.00000049, 0.5, 0.5, 0.5]
            payload = seed.generate_payloads(1, 42, (polygon,))[0]
        self.assertEqual(payload["coordinates"], {"longitude": 0.5, "latitude": 0.5})

    def test_corrupt_boundary_is_rejected(self) -> None:
        for data in (
            {},
            {"type": "Polygon", "coordinates": []},
            {"type": "MultiPolygon", "coordinates": []},
            {
                "type": "MultiPolygon",
                "coordinates": [[[[0, 0], [1, 0], [1, 1], [2, 2]]]],
            },
            {
                "type": "MultiPolygon",
                "coordinates": [[[[0, 0], [1, 0], [1, 999], [0, 0]]]],
            },
        ):
            with self.subTest(data=data), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "boundary.json"
                path.write_text(json.dumps(data))
                with self.assertRaises(ValueError):
                    seed.load_boundary(path)


class SeedCliTests(unittest.TestCase):
    def test_defaults_and_dry_run_make_no_http_requests(self) -> None:
        output = io.StringIO()
        with (
            redirect_stdout(output),
            patch("scripts.seed_lockers.build_opener") as http,
        ):
            self.assertEqual(seed.main(["--dry-run"]), 0)
        http.assert_not_called()
        payloads = json.loads(output.getvalue())
        self.assertEqual(len(payloads), 250)
        self.assertEqual(payloads[0]["location_id"], "DEMO-42-1")
        self.assertEqual(payloads[-1]["location_id"], "DEMO-42-250")
        other = io.StringIO()
        with redirect_stdout(other), patch("scripts.seed_lockers.build_opener") as http:
            self.assertEqual(seed.main(["--dry-run"]), 0)
        self.assertEqual(output.getvalue(), other.getvalue())
        http.assert_not_called()

    def test_invalid_options_are_rejected_before_reading_or_writing(self) -> None:
        options = (
            ["--count", "0"],
            ["--count", "-1"],
            ["--count", "1.5"],
            ["--seed", "1.5"],
            ["--base-url", "not-a-url"],
            ["--base-url", "file:///tmp/api"],
            ["--base-url", "https://"],
            ["--base-url", "https://user:password@example.org"],
            ["--base-url", "https://example.org?x=1"],
            ["--base-url", "https://example.org#fragment"],
            ["--base-url", "https://example.org:65536"],
            ["--base-url", "http://[::1]extra"],
            ["--base-url", "http://-invalid.example"],
            ["--base-url", "http://999.999.999.999"],
        )
        for arguments in options:
            with (
                self.subTest(arguments=arguments),
                redirect_stderr(io.StringIO()),
                patch("scripts.seed_lockers.load_boundary") as load,
                patch("scripts.seed_lockers.build_opener") as http,
            ):
                with self.assertRaises(SystemExit) as result:
                    seed.main(arguments)
                self.assertEqual(result.exception.code, 2)
                load.assert_not_called()
                http.assert_not_called()

    def test_invalid_geography_is_reported_before_http(self) -> None:
        errors = io.StringIO()
        with (
            redirect_stderr(errors),
            patch(
                "scripts.seed_lockers.load_boundary", side_effect=ValueError("geometry")
            ),
            patch("scripts.seed_lockers.build_opener") as http,
        ):
            self.assertEqual(seed.main(["--count", "1"]), 1)
        http.assert_not_called()
        self.assertIn("antes de escribir", errors.getvalue())

    def test_sequential_success_uses_configured_url_and_reports_confirmed_count(
        self,
    ) -> None:
        with (
            redirect_stderr(io.StringIO()) as errors,
            patch("scripts.seed_lockers.create_locker") as create,
        ):
            result = seed.main(
                ["--count", "3", "--seed", "7", "--base-url", "http://api.test/v1/"]
            )
        self.assertEqual(result, 0)
        self.assertEqual(create.call_count, 3)
        self.assertEqual(
            [call.args[1]["location_id"] for call in create.call_args_list],
            ["DEMO-7-1", "DEMO-7-2", "DEMO-7-3"],
        )
        self.assertEqual(
            {call.args[0] for call in create.call_args_list}, {"http://api.test/v1"}
        )
        self.assertIn("Confirmados: 3/3", errors.getvalue())
        self.assertIn("otra ejecución añade registros", errors.getvalue())

    def test_first_failed_or_uncertain_request_stops_without_retry(self) -> None:
        failures = (
            TimeoutError("timeout"),
            IncompleteRead(b'{"id":', 100),
            URLError("connection lost"),
            HTTPError("http://api.test/lockers", 503, "unavailable", Message(), None),
            ValueError("invalid response"),
        )
        for failure in failures:
            with (
                self.subTest(failure=failure),
                redirect_stderr(io.StringIO()) as errors,
                patch(
                    "scripts.seed_lockers.create_locker", side_effect=[None, failure]
                ) as create,
            ):
                self.assertEqual(seed.main(["--count", "3"]), 1)
                self.assertEqual(create.call_count, 2)
                self.assertIn("Confirmados: 1/3", errors.getvalue())
                self.assertIn("elemento 2 (DEMO-42-2)", errors.getvalue())
                self.assertIn("puede haberse creado", errors.getvalue())
                self.assertIn("No se reintenta ni se borra", errors.getvalue())


class SeedHttpTests(unittest.TestCase):
    def test_truncated_second_http_response_reports_only_first_confirmed_creation(
        self,
    ) -> None:
        with (
            redirect_stderr(io.StringIO()) as errors,
            patch("scripts.seed_lockers.build_opener") as factory,
        ):
            response = factory.return_value.open.return_value.__enter__.return_value
            response.status = 201
            response.read.side_effect = [
                b'{"id":"00000000-0000-4000-8000-000000000001"}',
                IncompleteRead(b'{"id":', 100),
            ]
            self.assertEqual(seed.main(["--count", "3"]), 1)
        self.assertEqual(factory.return_value.open.call_count, 2)
        self.assertIn("Confirmados: 1/3", errors.getvalue())
        self.assertIn("elemento 2 (DEMO-42-2)", errors.getvalue())
        self.assertIn("puede haberse creado", errors.getvalue())

    def test_request_contract_timeout_and_confirmed_response(self) -> None:
        payload = seed.generate_payloads(1, 42, seed.load_boundary())[0]
        with patch("scripts.seed_lockers.build_opener") as factory:
            response = factory.return_value.open.return_value.__enter__.return_value
            response.status = 201
            response.read.return_value = (
                b'{"id":"00000000-0000-4000-8000-000000000001"}'
            )
            seed.create_locker("http://api.test/v1", payload)
        request = factory.return_value.open.call_args.args[0]
        self.assertEqual(request.full_url, "http://api.test/v1/lockers")
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.get_header("Content-type"), "application/json")
        self.assertEqual(json.loads(request.data), payload)
        self.assertEqual(factory.return_value.open.call_args.kwargs, {"timeout": 10})
        self.assertIsInstance(factory.call_args.args[0], seed.NoRedirect)
        response.read.assert_called_once_with(seed.MAX_RESPONSE_BYTES + 1)
        self.assertEqual(UUID(json.loads(response.read.return_value)["id"]).version, 4)

    def test_unconfirmed_response_never_counts_as_success(self) -> None:
        payload = seed.generate_payloads(1, 42, seed.load_boundary())[0]
        for status, body in (
            (200, b"{}"),
            (201, b"not-json"),
            (201, b"[]"),
            (201, b'{"id":"invalid"}'),
            (201, b"{}"),
            (201, b"x" * (seed.MAX_RESPONSE_BYTES + 1)),
        ):
            with self.subTest(status=status, body=body[:20]):
                with patch("scripts.seed_lockers.build_opener") as factory:
                    response = (
                        factory.return_value.open.return_value.__enter__.return_value
                    )
                    response.status = status
                    response.read.return_value = body
                    with self.assertRaises(ValueError):
                        seed.create_locker("http://api.test", payload)
                factory.return_value.open.assert_called_once()

    def test_redirect_is_not_followed(self) -> None:
        self.assertIsNone(
            seed.NoRedirect().redirect_request(
                MagicMock(), None, 307, "redirect", {}, "http://other.test/lockers"
            )
        )
