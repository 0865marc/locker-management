"""CPython orchestration/fault checks; these do not emulate native D1 or Queues."""

import os
import subprocess
import sys
import unittest
from collections.abc import Sequence
from pathlib import Path

from bindings import Statement
from d1_probe import EXPECTED_CHECK, INSERT_CELL, verify_d1_batch
from queue_probe import process_spike_message

Value = str | int | float | None


class RecordingStatement:
    def __init__(self, database: "RecordingDatabase", query: str) -> None:
        self.database = database
        self.query = query
        self.values: tuple[Value, ...] = ()

    def bind(self, *values: Value) -> Statement:
        self.values = values
        self.database.events.append("bind")
        return self

    async def first(self) -> dict[str, object] | None:
        return self.database.rows.pop(0)

    async def run(self) -> dict[str, object]:
        self.database.events.append("write")
        if self.database.write_error is not None:
            raise self.database.write_error
        return {}


class RecordingDatabase:
    def __init__(self) -> None:
        self.events: list[str] = []
        self.rows: list[dict[str, object]] = [
            {"n": 3, "total": 6},
            {"n": 0},
            {"n": 1000},
        ]
        self.batches: list[list[RecordingStatement]] = []
        self.write_error: Exception | None = None
        self.positive_error: Exception | None = None
        self.negative_error: Exception | None = RuntimeError(EXPECTED_CHECK)
        self.negative_prepare_error: Exception | None = None

    def prepare(self, query: str) -> Statement:
        self.events.append("prepare")
        if len(self.batches) == 1 and query == INSERT_CELL:
            if self.negative_prepare_error is not None:
                raise self.negative_prepare_error
        return RecordingStatement(self, query)

    async def batch(self, statements: Sequence[Statement]) -> list[dict[str, object]]:
        prepared: list[RecordingStatement] = []
        for statement in statements:
            assert isinstance(statement, RecordingStatement)
            prepared.append(statement)
        self.batches.append(prepared)
        if len(self.batches) == 1 and self.positive_error is not None:
            raise self.positive_error
        if len(self.batches) == 2 and self.negative_error is not None:
            raise self.negative_error
        return [{} for _ in prepared]


class RecordingMessage:
    id = "unit-message"

    def __init__(self, events: list[str], marker: object) -> None:
        self.events = events
        self.payload = marker
        self.ack_error: Exception | None = None

    @property
    def body(self) -> object:
        self.events.append("body")
        return self.payload

    def ack(self) -> None:
        self.events.append("ack")
        if self.ack_error is not None:
            raise self.ack_error


class QueueProbeTests(unittest.IsolatedAsyncioTestCase):
    async def test_ack_precedes_body_and_all_database_work(self) -> None:
        database = RecordingDatabase()
        message = RecordingMessage(database.events, {"marker": "success-unit"})
        await process_spike_message(message, database)
        self.assertEqual(database.events, ["ack", "body", "prepare", "bind", "write"])

    async def test_ack_failure_prevents_body_access_and_database_work(self) -> None:
        database = RecordingDatabase()
        message = RecordingMessage(database.events, {"marker": "success-unit"})
        message.ack_error = RuntimeError("ack unavailable")
        with self.assertRaisesRegex(RuntimeError, "ack unavailable"):
            await process_spike_message(message, database)
        self.assertEqual(database.events, ["ack"])

    async def test_processing_failure_occurs_after_ack_and_single_write(self) -> None:
        database = RecordingDatabase()
        message = RecordingMessage(database.events, {"marker": "fail-unit"})
        with self.assertRaisesRegex(RuntimeError, "intentional failure after ack"):
            await process_spike_message(message, database)
        self.assertEqual(database.events, ["ack", "body", "prepare", "bind", "write"])

    async def test_database_error_propagates_after_ack_without_second_write(
        self,
    ) -> None:
        database = RecordingDatabase()
        database.write_error = RuntimeError("database unavailable")
        message = RecordingMessage(database.events, {"marker": "success-unit"})
        with self.assertRaisesRegex(RuntimeError, "database unavailable"):
            await process_spike_message(message, database)
        self.assertEqual(database.events, ["ack", "body", "prepare", "bind", "write"])

    async def test_invalid_message_is_acknowledged_before_validation(self) -> None:
        database = RecordingDatabase()
        message = RecordingMessage(database.events, {"marker": 42})
        with self.assertRaises(AssertionError):
            await process_spike_message(message, database)
        self.assertEqual(database.events, ["ack", "body"])


class QueueEntrypointTests(unittest.TestCase):
    def test_actual_callback_forms_keep_instance_bindings_ack_order_and_context(
        self,
    ) -> None:
        script = """
import asyncio, sys, types
workers = types.ModuleType('workers')
workers.WorkerEntrypoint = type('WorkerEntrypoint', (), {})
workers.Request = type('Request', (), {})
workers.asgi = types.ModuleType('workers.asgi')
sys.modules['workers'] = workers
from test_probe_units import RecordingDatabase, RecordingMessage
import worker
from event_context import current_environment
async def check():
    entrypoint = worker.Default()
    for complete in (False, True):
        for outcome in ('success', 'ack-failure', 'process-failure'):
            database = RecordingDatabase()
            raw_database = RecordingDatabase()
            environment = types.SimpleNamespace(DB=database, QUOTATIONS=object(), LABEL='instance')
            raw_environment = types.SimpleNamespace(DB=raw_database, QUOTATIONS=object(), LABEL='raw-callback')
            entrypoint.env = environment
            marker = 'fail-unit' if outcome == 'process-failure' else 'success-unit'
            class ScopedMessage(RecordingMessage):
                def ack(self):
                    assert current_environment.get() is environment
                    super().ack()
                @property
                def body(self):
                    assert current_environment.get() is environment
                    return super().body
            message = ScopedMessage(database.events, {'marker':marker})
            if outcome == 'ack-failure':
                message.ack_error = OSError('ack failed')
            batch = types.SimpleNamespace(messages=[message])
            prior = object()
            token = current_environment.set(prior)
            try:
                try:
                    if complete:
                        await entrypoint.queue(batch, raw_environment, object())
                    else:
                        await entrypoint.queue(batch)
                except (OSError, RuntimeError):
                    assert outcome != 'success'
                else:
                    assert outcome == 'success'
                assert current_environment.get() is prior
                assert database.events == (['ack'] if outcome == 'ack-failure' else ['ack','body','prepare','bind','write'])
                assert raw_database.events == []
            finally:
                current_environment.reset(token)
            try:
                current_environment.get()
            except LookupError:
                pass
            else:
                raise AssertionError('event context leaked')
asyncio.run(check())
"""
        root = Path(__file__).resolve().parents[3]
        environment = {
            **os.environ,
            "PYTHONPATH": os.pathsep.join(
                (
                    str(root / "deploy/cloudflare/runtime_spike"),
                    str(root / "deploy/cloudflare/tests"),
                    str(root / "backend"),
                )
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


class D1ProbeControlTests(unittest.IsolatedAsyncioTestCase):
    async def test_positive_and_named_middle_failure_controls_are_executed(
        self,
    ) -> None:
        database = RecordingDatabase()
        result = await verify_d1_batch(database)
        self.assertEqual(result["positive_batch_count"], 3)
        self.assertEqual(result["expected_check"], "spike_value_nonnegative")
        self.assertEqual(result["json_each_count"], 1000)
        self.assertEqual(len(database.batches), 3)
        for number, values in [(0, [1, 2, 3]), (1, [1, -1, 3])]:
            batch = database.batches[number]
            self.assertEqual(
                [statement.query for statement in batch], [INSERT_CELL] * 3
            )
            self.assertEqual([statement.values[1] for statement in batch], values)
        self.assertEqual(len(database.batches[2]), 1)
        self.assertEqual(len(database.batches[2][0].values), 1)

    async def test_initial_batch_failure_cannot_be_reported_as_rollback(self) -> None:
        database = RecordingDatabase()
        # Even the expected CHECK is invalid during the positive control.
        database.positive_error = RuntimeError(EXPECTED_CHECK)
        with self.assertRaisesRegex(RuntimeError, EXPECTED_CHECK):
            await verify_d1_batch(database)
        self.assertEqual(len(database.batches), 1)

    async def test_positive_control_must_commit_all_bound_values(self) -> None:
        database = RecordingDatabase()
        database.rows[0] = {"n": 0, "total": None}
        with self.assertRaises(AssertionError):
            await verify_d1_batch(database)
        self.assertEqual(len(database.batches), 1)

    async def test_negative_prepare_error_is_not_a_rollback_result(self) -> None:
        database = RecordingDatabase()
        database.negative_prepare_error = RuntimeError(EXPECTED_CHECK)
        with self.assertRaisesRegex(RuntimeError, EXPECTED_CHECK):
            await verify_d1_batch(database)
        self.assertEqual(len(database.batches), 1)

    async def test_transport_and_unrelated_constraints_are_not_accepted(self) -> None:
        for error in (
            "transport unavailable",
            "CHECK constraint failed: another_check",
        ):
            with self.subTest(error=error):
                database = RecordingDatabase()
                database.negative_error = RuntimeError(error)
                with self.assertRaisesRegex(RuntimeError, error):
                    await verify_d1_batch(database)
                self.assertEqual(len(database.batches), 2)

    async def test_missing_constraint_failure_is_rejected(self) -> None:
        database = RecordingDatabase()
        database.negative_error = None
        with self.assertRaisesRegex(AssertionError, "intentionally invalid middle"):
            await verify_d1_batch(database)

    async def test_partial_writes_after_expected_failure_are_rejected(self) -> None:
        database = RecordingDatabase()
        database.rows[1] = {"n": 1}
        with self.assertRaises(AssertionError):
            await verify_d1_batch(database)
        self.assertEqual(len(database.batches), 2)


if __name__ == "__main__":
    unittest.main()
