"""Read-only compatibility guard on an actual populated Wrangler D1 history."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import cast
from unittest.mock import patch

from check_schema import history_from_response, inspect_history, validate_history

ROOT = Path(__file__).resolve().parents[2]
CLOUDFLARE = ROOT / "cloudflare"
CONFIG = CLOUDFLARE / "wrangler.production.jsonc"
WRANGLER = ["node", str(CLOUDFLARE / "node_modules/wrangler/bin/wrangler.js")]


class SchemaGuardTests(unittest.TestCase):
    def test_reject_incomplete_unknown_and_unreadable_histories(self) -> None:
        for applied in ((), ("0002_unknown.sql",), ("0001_initial.sql", "0002.sql")):
            with self.subTest(applied=applied), self.assertRaises(ValueError):
                validate_history(("0001_initial.sql",), applied)
        empty_response: list[object] = []
        empty_rows: list[object] = []
        failed_record: dict[str, object] = {"success": False, "results": empty_rows}
        malformed_record: dict[str, object] = {
            "success": True,
            "results": [{"name": 1}],
        }
        invalid_responses: tuple[object, ...] = (
            None,
            empty_response,
            [failed_record],
            [malformed_record],
        )
        for value in invalid_responses:
            with self.subTest(value=value), self.assertRaises(ValueError):
                history_from_response(value)

    def test_native_populated_history_compatible_and_mismatch_are_read_only(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="locker-schema-guard-") as directory:
            state = Path(directory)
            with patch.dict(
                os.environ,
                {
                    "XDG_CONFIG_HOME": str(state / "config"),
                    "XDG_CACHE_HOME": str(state / "cache"),
                    "WRANGLER_SEND_METRICS": "false",
                },
            ):
                base = [
                    "--config",
                    str(CONFIG),
                    "--local",
                    "--persist-to",
                    str(state / "d1"),
                ]

                def run(arguments: list[str]) -> subprocess.CompletedProcess[str]:
                    result = subprocess.run(
                        WRANGLER + arguments,
                        cwd=CLOUDFLARE,
                        capture_output=True,
                        text=True,
                        timeout=45,
                    )
                    self.assertEqual(
                        result.returncode, 0, result.stderr + result.stdout
                    )
                    return result

                run(["d1", "migrations", "apply", "locker-management-demo", *base])
                run(
                    [
                        "d1",
                        "execute",
                        "locker-management-demo",
                        *base,
                        "--command",
                        "INSERT INTO deliveries (id, tracking_number, carrier_code, recipient_name, received_at, status) "
                        "VALUES ('00000000-0000-0000-0000-000000000001', 'guard-probe', 'C', 'Ana', "
                        "'2026-10-17T00:00:00.000000Z', 'AWAITING_PICKUP')",
                    ]
                )

                def data() -> list[object]:
                    result = run(
                        [
                            "d1",
                            "execute",
                            "locker-management-demo",
                            *base,
                            "--json",
                            "--command",
                            "SELECT id, tracking_number FROM deliveries",
                        ]
                    )
                    decoded: object = json.loads(result.stdout)
                    assert isinstance(decoded, list)
                    record = cast(list[object], decoded)[0]
                    assert isinstance(record, dict)
                    rows = cast(dict[str, object], record)["results"]
                    assert isinstance(rows, list)
                    return cast(list[object], rows)

                expected = tuple(
                    path.name
                    for path in sorted((CLOUDFLARE / "migrations").glob("*.sql"))
                )
                history = inspect_history(
                    "locker-management-demo", CONFIG, persist_to=state / "d1"
                )
                before = data()
                validate_history(expected, history)
                command = [
                    sys.executable,
                    str(ROOT / "scripts/cloudflare/check_schema.py"),
                    "--persist-to",
                    str(state / "d1"),
                ]
                accepted = subprocess.run(
                    command, capture_output=True, text=True, timeout=45
                )
                self.assertEqual(accepted.returncode, 0, accepted.stderr)
                incompatible = state / "incompatible-release"
                incompatible.mkdir()
                (incompatible / "9999_incompatible.sql").write_text(
                    "-- Never applied\n"
                )
                rejected = subprocess.run(
                    command + ["--migrations", str(incompatible)],
                    capture_output=True,
                    text=True,
                    timeout=45,
                )
                self.assertNotEqual(rejected.returncode, 0)
                self.assertIn("incompatible", rejected.stderr)
                self.assertEqual(
                    inspect_history(
                        "locker-management-demo", CONFIG, persist_to=state / "d1"
                    ),
                    history,
                )
                self.assertEqual(data(), before)
                self.assertEqual(history, expected)
                self.assertEqual(len(before), 1)


if __name__ == "__main__":
    unittest.main()
