"""Complete source-backed locations, reproducible generation and HTTP outcomes."""

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


class SeedCatalogueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.locations = seed.load_catalogue()
        cls.catalogue = json.loads(seed.CATALOGUE_PATH.read_text(encoding="utf-8"))

    def test_thousand_payloads_are_reproducible_complete_and_exact_source_pairs(
        self,
    ) -> None:
        payloads = seed.generate_payloads(1000, 42, self.locations)
        self.assertEqual(len(payloads), 1000)
        self.assertEqual(payloads, seed.generate_payloads(1000, 42, self.locations))
        self.assertNotEqual(payloads[:3], seed.generate_payloads(3, 43, self.locations))
        self.assertEqual(len(self.locations), 3423)
        self.assertEqual(
            len({location.source_province_id for location in self.locations}), 52
        )
        pairs = {
            (
                json.dumps(location.address, sort_keys=True),
                json.dumps(location.coordinates, sort_keys=True),
            )
            for location in self.locations
        }
        seen_pairs = set()
        for index, payload in enumerate(payloads, start=1):
            pair = (
                json.dumps(payload["address"], sort_keys=True),
                json.dumps(payload["coordinates"], sort_keys=True),
            )
            self.assertIn(pair, pairs)
            seen_pairs.add(pair)
            parsed = CreateLocker.model_validate(payload)
            self.assertIs(parsed.active, True)
            self.assertIsNotNone(parsed.address)
            self.assertEqual(parsed.location_id, f"DEMO-42-{index}")
            self.assertEqual(len(parsed.compartments), 1)
            batch = parsed.compartments[0]
            self.assertEqual(batch.quantity, 6)
            self.assertIs(batch.enabled, True)
            self.assertEqual(
                batch.dimensions.model_dump(),
                {"width_mm": 400, "height_mm": 400, "depth_mm": 600},
            )
            self.assertEqual(
                set(payload),
                {"location_id", "active", "address", "coordinates", "compartments"},
            )
        self.assertEqual(len(seen_pairs), 1000)

    def test_every_normalized_field_matches_its_preserved_source_record(self) -> None:
        for location, raw in zip(
            self.locations, self.catalogue["records"], strict=True
        ):
            self.assertEqual(location.source_id, raw["IDEESS"])
            self.assertEqual(location.source_address, raw["Dirección"])
            self.assertEqual(location.source_latitude, raw["Latitud"])
            self.assertEqual(location.source_longitude, raw["Longitud (WGS84)"])
            self.assertEqual(location.address["postal_code"], raw["C.P."])
            self.assertEqual(location.address["postal_code"][:2], raw["IDProvincia"])
            self.assertEqual(location.address["city"], raw["Localidad"])
            self.assertEqual(location.address["province"], raw["Provincia"])
            self.assertEqual(location.address["country_code"], "ES")
            street, number = raw["Dirección"].split(",")
            self.assertEqual(location.address["street"], street)
            self.assertEqual(location.address["street_number"], number.strip())
            self.assertEqual(
                location.coordinates["latitude"],
                float(raw["Latitud"].replace(",", ".")),
            )
            self.assertEqual(
                location.coordinates["longitude"],
                float(raw["Longitud (WGS84)"].replace(",", ".")),
            )
        # Concrete pinned-source example, preserving the leading-zero postal code.
        example = next(
            location for location in self.locations if location.source_id == "4375"
        )
        self.assertEqual(
            example.address,
            {
                "country_code": "ES",
                "postal_code": "02250",
                "province": "ALBACETE",
                "city": "ABENGIBRE",
                "street": "AVENIDA CASTILLA LA MANCHA",
                "street_number": "26",
            },
        )
        self.assertEqual(
            example.coordinates, {"latitude": 39.211417, "longitude": -1.539167}
        )
        self.assertNotIn("12883", {location.source_id for location in self.locations})

    def test_rounds_exhaust_all_records_before_repeating_and_do_not_mutate_catalogue(
        self,
    ) -> None:
        locations = self.locations[:3]
        before = json.dumps([location.address for location in locations])
        payloads = seed.generate_payloads(8, 7, locations)
        pairs = [(payload["address"], payload["coordinates"]) for payload in payloads]
        expected = [(location.address, location.coordinates) for location in locations]
        for start in (0, 3):
            self.assertCountEqual(pairs[start : start + 3], expected)
        self.assertEqual(len(payloads), 8)
        self.assertEqual(len({item["location_id"] for item in payloads}), 8)
        payloads[0]["address"]["street"] = "changed locally"
        self.assertEqual(
            json.dumps([location.address for location in locations]), before
        )

    def test_ambiguous_addresses_are_excluded_instead_of_inventing_numbers(
        self,
    ) -> None:
        example = self.catalogue["records"][0]
        for address in (
            "CR CM-332, 46,4",
            "CARRETERA A-1 KM 14",
            "CALLE MAYOR",
            "CALLE MAYOR, S/N",
            "CALLE MAYOR, 1,4",
        ):
            with self.subTest(address=address), self.assertRaises(ValueError):
                seed.source_record({**example, "Dirección": address})
        self.assertEqual(
            seed.source_record({**example, "Dirección": "CALLE MAYOR, 14B"}).address[
                "street_number"
            ],
            "14B",
        )

    def test_invalid_or_duplicate_catalogue_records_fail_before_any_http(self) -> None:
        example = self.catalogue["records"][0]
        invalid_rows = [
            {**example, "Dirección": "CR CM-332, 46,4"},
            {**example, "IDEESS": ""},
            {**example, "IDEESS": "unknown"},
            {**example, "C.P.": 2250},
            {**example, "C.P.": "28001"},
            {**example, "Provincia": ""},
            {**example, "Municipio": ""},
            {**example, "Localidad": None},
            {**example, "Latitud": "NaN"},
            {**example, "Latitud": "91,0"},
            {**example, "Longitud (WGS84)": "Infinity"},
            {**example, "Latitud": "0", "Longitud (WGS84)": "0"},
        ]
        invalid_catalogues = [
            {},
            {**self.catalogue, "records": []},
            {
                **self.catalogue,
                "source": {
                    "snapshot_date": "unknown",
                    "snapshot_sha256": seed.SNAPSHOT_SHA256,
                },
            },
            {**self.catalogue, "records": [example, example]},
            *[
                {**self.catalogue, "records": [example, invalid]}
                for invalid in invalid_rows
            ],
        ]
        real_load = seed.load_catalogue
        for catalogue in invalid_catalogues:
            with (
                self.subTest(catalogue=str(catalogue)[-100:]),
                tempfile.TemporaryDirectory() as directory,
            ):
                path = Path(directory) / "catalogue.json"
                path.write_text(json.dumps(catalogue), encoding="utf-8")
                with (
                    redirect_stderr(io.StringIO()) as errors,
                    patch(
                        "scripts.seed_lockers.load_catalogue",
                        side_effect=lambda: real_load(path),
                    ),
                    patch("scripts.seed_lockers.build_opener") as http,
                ):
                    self.assertEqual(seed.main(["--count", "2"]), 1)
                http.assert_not_called()
                self.assertIn("antes de escribir", errors.getvalue())

    def test_catalogue_fingerprint_matches_documented_extract(self) -> None:
        import hashlib

        self.assertEqual(
            hashlib.sha256(seed.CATALOGUE_PATH.read_bytes()).hexdigest(),
            "5fa87d383d0f42cfa48f032098b0210731461e838f6fdd8e4107a345900d01d6",
        )
        self.assertEqual(self.catalogue["source"]["snapshot_date"], seed.SNAPSHOT_DATE)
        self.assertEqual(
            self.catalogue["source"]["snapshot_sha256"], seed.SNAPSHOT_SHA256
        )


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
                patch("scripts.seed_lockers.load_catalogue") as load,
                patch("scripts.seed_lockers.build_opener") as http,
            ):
                with self.assertRaises(SystemExit) as result:
                    seed.main(arguments)
                self.assertEqual(result.exception.code, 2)
                load.assert_not_called()
                http.assert_not_called()

    def test_unreadable_catalogue_is_reported_before_http(self) -> None:
        errors = io.StringIO()
        with (
            redirect_stderr(errors),
            patch(
                "scripts.seed_lockers.load_catalogue",
                side_effect=OSError("unreadable catalogue"),
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
        payload = seed.generate_payloads(1, 42, seed.load_catalogue())[0]
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
        payload = seed.generate_payloads(1, 42, seed.load_catalogue())[0]
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
