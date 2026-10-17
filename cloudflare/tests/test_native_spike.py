"""Run against the native runtime; an unavailable runtime is an error."""

import json
import os
import time
import unittest
import urllib.error
import urllib.request
from typing import cast
from uuid import uuid4

BASE_URL = os.environ.get("SPIKE_BASE_URL", "http://127.0.0.1:8787")
CLIENT = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def request(path: str, body: object | None = None) -> tuple[int, dict[str, object]]:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        BASE_URL + path,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        response = CLIENT.open(req, timeout=60)
    except urllib.error.HTTPError as error:
        response = error
    with response:
        value: object = json.load(response)
        assert isinstance(value, dict)
        status: object = response.status
        assert isinstance(status, int)
        return status, cast(dict[str, object], value)


class NativeSpikeTests(unittest.TestCase):
    def test_real_schemas_and_single_application(self) -> None:
        status, health = request("/")
        self.assertEqual(status, 200)
        self.assertEqual(health["app_builds"], 1)
        self.assertEqual(health["forbidden_imports"], [])
        schemas = health["schemas"]
        python_version = health["python"]
        assert isinstance(schemas, list)
        assert isinstance(python_version, str)
        self.assertEqual(len(cast(list[object], schemas)), 4)
        self.assertIn("3.13", python_version)
        dimensions = {"width_mm": 100, "height_mm": 100, "depth_mm": 100}
        for count, expected in [(1000, 200), (1001, 422)]:
            status, _ = request(
                "/validate",
                {
                    "location_id": "native-test",
                    "compartments": [{"quantity": count, "dimensions": dimensions}],
                },
            )
            self.assertEqual(status, expected)
        self.assertEqual(request("/")[1]["app_builds"], 1)
        self.assertEqual(request("/openapi.json")[0], 200)

    def test_native_asgi_context_and_exception_cleanup(self) -> None:
        status, result = request("/context-check")
        self.assertEqual(status, 200)
        self.assertTrue(result["isolated"])
        self.assertTrue(result["exception_reset"])
        self.assertEqual(result["app_builds"], 1)

    def test_native_d1_rollback_and_json_each(self) -> None:
        status, result = request("/d1-check", {})
        self.assertEqual(status, 200)
        self.assertTrue(result["rollback"])
        self.assertEqual(result["json_each_count"], 1000)

    def test_native_python_queue_send_ack_then_failure_without_retry(self) -> None:
        markers = [f"success-{uuid4()}", f"fail-{uuid4()}"]
        for marker in markers:
            self.assertEqual(request(f"/publish/{marker}", {})[0], 200)
            deadline = time.monotonic() + 15
            while True:
                status, result = request(f"/queue-events/{marker}")
                self.assertEqual(status, 200)
                if result["n"] == 1:
                    break
                self.assertLess(time.monotonic(), deadline, result)
                time.sleep(0.05)
            self.assertEqual(result["ack_sync"], 1)
        time.sleep(1)
        for marker in markers:
            self.assertEqual(request(f"/queue-events/{marker}")[1]["n"], 1)

    def test_measure_representative_real_schema_work(self) -> None:
        samples: list[dict[str, object]] = []
        for count in (1, 1000, 2000):
            for _ in range(3):
                started = time.perf_counter()
                status, result = request(f"/benchmark/{count}")
                self.assertEqual(status, 200)
                self.assertEqual(result["count"], count)
                result["http_wall_ms"] = (time.perf_counter() - started) * 1000
                samples.append(result)
        print("NATIVE_BENCHMARK=" + json.dumps(samples, sort_keys=True))


if __name__ == "__main__":
    unittest.main(verbosity=2)
