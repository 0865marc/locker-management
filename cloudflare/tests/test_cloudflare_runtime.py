"""Official production Python Worker HTTP/Queues contracts; no skip fallback."""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts/cloudflare"))
from acceptance import Campaign, HttpRequest


class NativeRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_production_http_queue_persistence_campaign(self) -> None:
        base_url = os.environ.get("CLOUDFLARE_RUNTIME_BASE_URL")
        if not base_url:
            self.fail(
                "Run cloudflare/tests/run_runtime.py to provide the required Python Worker"
            )
        assert base_url is not None
        result = await Campaign(HttpRequest(base_url)).run()
        self.assertTrue(result["samples"])
        self.assertIsNone(result["remote_cpu_ms"])
