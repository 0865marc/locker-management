"""Event isolation and the native boundary, independently of the WASM runtime."""

import asyncio
import subprocess
import sys
import unittest
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock

from starlette.types import Message, Receive, Scope, Send

from adapters.database.d1.bindings import D1BindingError, D1PreparedStatement, D1Value
from adapters.database.d1.native import NativeDatabase
from adapters.queue.cloudflare import NativeMessage, QueueMessage
from adapters.runtime.cloudflare import (
    EventBindings,
    event_scope,
    get_database,
    get_environment,
    get_queue,
)
from application.persistence import PersistenceError
from application.quotations.use_cases import QuotationProcessor
from entrypoints.cloudflare_consumer import consume_batch


class Statement:
    def __init__(self, database: "Database") -> None:
        self.database = database

    def bind(self, *values: D1Value) -> "Statement":
        return self

    async def first(self) -> object:
        return None

    async def all(self) -> object:
        return {"results": [], "meta": {"changes": 0}}

    async def run(self) -> object:
        if self.database.error is not None:
            raise self.database.error
        return {"results": [], "meta": {"changes": 1}}


class Database:
    def __init__(self) -> None:
        self.queries: list[str] = []
        self.error: Exception | None = None

    def prepare(self, query: str) -> Statement:
        self.queries.append(query)
        return Statement(self)

    async def batch(self, statements: Sequence[D1PreparedStatement]) -> object:
        if self.error is not None:
            raise self.error
        assert all(isinstance(statement, Statement) for statement in statements)
        return [{"results": [], "meta": {"changes": 1}} for _ in statements]


class Queue:
    async def send(self, body: dict[str, str]) -> None:
        return None


@dataclass
class Environment:
    DB: Database
    QUOTATIONS: Queue


async def receive() -> Message:
    return {"type": "http.request", "body": b""}


async def send(message: Message) -> None:
    return None


class CloudflareContextTests(unittest.IsolatedAsyncioTestCase):
    async def test_same_task_scope_restores_absence_prior_value_and_exception(
        self,
    ) -> None:
        first, second = (
            Environment(Database(), Queue()),
            Environment(Database(), Queue()),
        )
        with self.assertRaises(PersistenceError):
            get_database()
        for fails in (False, True):
            with self.subTest(fails=fails):
                try:
                    with event_scope(first):
                        self.assertIs(get_database(), first.DB)
                        with event_scope(second):
                            self.assertIs(get_queue(), second.QUOTATIONS)
                        self.assertIs(get_environment(), first)
                        if fails:
                            raise ValueError("intentional")
                except ValueError:
                    self.assertTrue(fails)
                with self.assertRaises(PersistenceError):
                    get_environment()

    async def test_concurrent_http_events_use_only_their_own_bindings(self) -> None:
        first, second = (
            Environment(Database(), Queue()),
            Environment(Database(), Queue()),
        )
        ready, release = asyncio.Event(), asyncio.Event()
        entered = 0

        async def application(scope: Scope, receive: Receive, send: Send) -> None:
            nonlocal entered
            initial = get_environment()
            get_database().prepare(scope["path"] + "-before")
            entered += 1
            if entered == 2:
                ready.set()
            await release.wait()
            self.assertIs(get_environment(), initial)
            get_database().prepare(scope["path"] + "-after")
            if scope["path"] == "/failure":
                raise ValueError("intentional")

        wrapped = EventBindings(application)

        async def invoke(environment: Environment, path: str) -> None:
            try:
                await wrapped(
                    {"type": "http", "path": path, "env": environment}, receive, send
                )
            finally:
                # Inspect the same task that called middleware, not its parent.
                with self.assertRaises(PersistenceError):
                    get_environment()

        tasks = [
            asyncio.create_task(invoke(first, "/success")),
            asyncio.create_task(invoke(second, "/failure")),
        ]
        try:
            await asyncio.wait_for(ready.wait(), timeout=2)
        finally:
            release.set()
            results = await asyncio.gather(*tasks, return_exceptions=True)
        self.assertIsNone(results[0])
        self.assertIsInstance(results[1], ValueError)
        self.assertEqual(first.DB.queries, ["/success-before", "/success-after"])
        self.assertEqual(second.DB.queries, ["/failure-before", "/failure-after"])
        with event_scope(first):
            self.assertIs(get_database(), first.DB)

    async def test_native_boundary_preserves_results_and_only_translates_binding_errors(
        self,
    ) -> None:
        database = Database()
        native = NativeDatabase(database, (OSError,))
        statement = native.prepare("query").bind(1)
        self.assertEqual(await statement.run(), {"results": [], "meta": {"changes": 1}})
        self.assertEqual(
            await native.batch([statement]), [{"results": [], "meta": {"changes": 1}}]
        )
        database.error = OSError("native transport failure")
        with self.assertRaises(D1BindingError):
            await statement.run()
        with self.assertRaises(D1BindingError):
            await native.batch([statement])
        database.error = TypeError("programming error")
        with self.assertRaisesRegex(TypeError, "programming error"):
            await statement.run()


class NativeQueueBodyTests(unittest.IsolatedAsyncioTestCase):
    async def test_python_payload_keys_do_not_trigger_proxy_conversion(self) -> None:
        payload = {"to_py": "not a proxy method"}

        class Message:
            def ack(self) -> None:
                return None

            @property
            def body(self) -> object:
                return payload

        self.assertIs(NativeMessage(Message()).body, payload)

    async def test_body_proxy_is_decoded_after_ack_and_not_if_ack_fails(self) -> None:
        events: list[str] = []

        class Body:
            def to_py(self) -> object:
                events.append("decode")
                return {"quotation_id": "00000000-0000-0000-0000-000000000001"}

        class Message:
            fail = False

            def ack(self) -> None:
                events.append("ack")
                if self.fail:
                    raise OSError("ack failed")

            @property
            def body(self) -> object:
                events.append("body")
                return Body()

        environment = Environment(Database(), Queue())
        prior = Environment(Database(), Queue())

        async def process(quotation_id: object) -> None:
            self.assertIs(get_environment(), environment)
            events.append("process")
            await asyncio.sleep(0)

        processor = AsyncMock(spec=QuotationProcessor)
        processor.process.side_effect = process
        message = Message()

        @dataclass
        class Batch:
            messages: Sequence[QueueMessage]

        with event_scope(prior):
            await consume_batch(Batch([message, message]), environment, processor)
            self.assertIs(get_environment(), prior)
        self.assertEqual(events, ["ack", "body", "decode", "process"] * 2)
        self.assertEqual(processor.process.await_count, 2)
        events.clear()
        processor.process.reset_mock()
        message.fail = True
        with self.assertRaises(OSError):
            await consume_batch(Batch([message]), environment, processor)
        self.assertEqual(events, ["ack"])
        processor.process.assert_not_awaited()
        with self.assertRaises(PersistenceError):
            get_environment()
        events.clear()
        message.fail = False
        processor.process.side_effect = ValueError("processing failed")
        with event_scope(prior):
            with self.assertRaisesRegex(ValueError, "processing failed"):
                await consume_batch(Batch([message, message]), environment, processor)
            self.assertIs(get_environment(), prior)
        self.assertEqual(events, ["ack", "body", "decode"])
        with self.assertRaises(PersistenceError):
            get_environment()


class CloudflareImportTests(unittest.TestCase):
    def test_production_import_builds_app_without_accessing_bindings_or_other_profile(
        self,
    ) -> None:
        # SDK shims allow checking the actual composition graph under CPython;
        # this is explicitly not a Workers/ASGI runtime compatibility test.
        script = """
import sys, types
import asyncio
from unittest.mock import patch, AsyncMock
workers = types.ModuleType('workers')
workers.WorkerEntrypoint = type('WorkerEntrypoint', (), {})
workers.Request = type('Request', (), {})
workers.asgi = types.ModuleType('workers.asgi')
pyodide = types.ModuleType('pyodide')
ffi = types.ModuleType('pyodide.ffi')
ffi.JsException = type('JsException', (Exception,), {})
sys.modules.update({'workers':workers,'pyodide':pyodide,'pyodide.ffi':ffi})
import adapters.runtime.cloudflare as context
with patch.object(context,'get_database', side_effect=AssertionError('import DB access')), patch.object(context,'get_queue', side_effect=AssertionError('import queue access')):
    from entrypoints import cloudflare_api
    application = cloudflare_api.app
    assert cloudflare_api.event_app.application is application
    assert application.state.quotation_service.repository is cloudflare_api.quotation_repository
    assert cloudflare_api.processor.repository is cloudflare_api.quotation_repository
async def check_delegate():
    worker = cloudflare_api.Default()
    environment = object()
    worker.env = environment
    batch = object()
    with patch.object(cloudflare_api, 'consume_batch', new_callable=AsyncMock) as consume:
        await worker.queue(batch)
        await worker.queue(batch)
        assert consume.await_count == 2
        consume.assert_awaited_with(batch, environment, cloudflare_api.processor)
    assert cloudflare_api.app is application
    assert cloudflare_api.processor.repository is cloudflare_api.quotation_repository
asyncio.run(check_delegate())
for name in ('entrypoints.api','entrypoints.rabbitmq_consumer','sqlmodel','asyncpg','alembic','aio_pika'):
    assert name not in sys.modules, name
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            cwd=Path(__file__).resolve().parents[2],
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_consumer_import_is_independent_of_http_and_runtime_sdk(self) -> None:
        script = """
import sys
from datetime import datetime, timezone
from unittest.mock import AsyncMock
from application.quotations.ports import QuotationRepository
from entrypoints.cloudflare_consumer import create_processor
repository = AsyncMock(spec=QuotationRepository)
clock = lambda: datetime.now(timezone.utc)
processor = create_processor(repository, clock)
assert processor.repository is repository
assert processor.clock is clock
assert repository.mock_calls == []
for name in ('composition', 'entrypoints.cloudflare_api', 'entrypoints.api',
             'fastapi', 'workers', 'pyodide', 'sqlmodel', 'asyncpg', 'aio_pika'):
    assert name not in sys.modules, name
"""
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            cwd=Path(__file__).resolve().parents[2],
        )
        self.assertEqual(result.returncode, 0, result.stderr)
