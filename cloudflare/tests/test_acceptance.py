"""Campaign resource ceilings stop auxiliary HTTP traffic before overrun."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/cloudflare"))
from acceptance import Campaign


class AcceptanceBudgetTests(unittest.IsolatedAsyncioTestCase):
    async def test_request_cap_prevents_the_next_network_operation(self) -> None:
        calls: list[str] = []

        async def request(
            method: str, path: str, body: object | None = None
        ) -> tuple[int, object]:
            calls.append(path)
            return 200, {}

        campaign = Campaign(request, max_requests=1)
        await campaign.call("GET", "/openapi.json")
        with self.assertRaisesRegex(RuntimeError, "budget reached"):
            await campaign.call("GET", "/lockers")
        self.assertEqual(calls, ["/openapi.json"])

    async def test_override_cannot_increase_the_campaign_ceiling(self) -> None:
        async def request(
            method: str, path: str, body: object | None = None
        ) -> tuple[int, object]:
            raise AssertionError("Invalid campaign must not perform I/O")

        for maximum in (0, -1, 1001):
            with self.assertRaises(ValueError):
                Campaign(request, max_requests=maximum)

    async def test_required_case_failure_stops_the_campaign(self) -> None:
        calls: list[str] = []

        async def request(
            method: str, path: str, body: object | None = None
        ) -> tuple[int, object]:
            calls.append(path)
            return 503, {}

        with self.assertRaisesRegex(AssertionError, "received 503"):
            await Campaign(request).run()
        self.assertEqual(calls, ["/docs"])
