"""Actual spike code under controlled clocks and platform import doubles."""

import os
import subprocess
import sys
import unittest
from pathlib import Path


class StartupClockTests(unittest.TestCase):
    def test_zero_origin_frozen_and_positive_measurements(self) -> None:
        script = """
import asyncio, sys, types
from unittest.mock import patch
workers = types.ModuleType('workers')
workers.WorkerEntrypoint = type('WorkerEntrypoint', (), {})
workers.Request = type('Request', (), {})
workers.asgi = types.ModuleType('workers.asgi')
sys.modules['workers'] = workers
import importlib
original_import = importlib.import_module
def load(name, *args, **kwargs):
    if name == 'worker':
        assert sys.modules['import_clock'].STARTED == 0
        assert 'worker' not in sys.modules
    return original_import(name, *args, **kwargs)
with patch('time.perf_counter', return_value=0), patch('importlib.import_module', side_effect=load):
    import bootstrap
    import import_clock
    import worker
assert bootstrap.Default is worker.Default
assert worker.IMPORT_WALL_MS is None
assert worker.IMPORT_UNAVAILABLE_REASON == 'runtime clock did not advance'
assert import_clock.elapsed_ms(-5, -4) == (1000, None)
with patch('time.perf_counter', return_value=1):
    importlib.reload(worker)
assert worker.IMPORT_WALL_MS == 1000
assert worker.IMPORT_UNAVAILABLE_REASON is None
async def check():
    for count in (1, 1000, 2000):
        with patch.object(worker, 'perf_counter', return_value=0):
            result = await worker.benchmark(count)
        for field in ('validation_wall_ms', 'response_construction_wall_ms', 'serialization_wall_ms'):
            assert result[field] is None
            assert result[field + '_unavailable_reason'] == 'runtime clock did not advance'
        assert result['timing_source'] == 'runtime perf_counter delta; not CPU'
    with patch.object(worker, 'perf_counter', side_effect=[0, 1, 2, 3, 4, 5]):
        result = await worker.benchmark(1)
    for field in ('validation_wall_ms', 'response_construction_wall_ms', 'serialization_wall_ms'):
        assert result[field] == 1000
        assert result[field + '_unavailable_reason'] is None
asyncio.run(check())
"""
        root = Path(__file__).resolve().parents[3]
        environment = {
            **os.environ,
            "PYTHONPATH": os.pathsep.join(
                (str(root / "deploy/cloudflare/runtime_spike"), str(root / "backend"))
            ),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=root,
            env=environment,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
