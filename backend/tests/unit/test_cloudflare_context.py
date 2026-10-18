"""Event isolation and the native boundary, independently of the WASM runtime."""

import asyncio
import subprocess
import sys
import unittest
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock, patch

from starlette.types import Message, Receive, Scope, Send

from adapters.database.d1.bindings import D1BindingError, D1PreparedStatement, D1Value
from adapters.database.d1.native import NativeDatabase
from adapters.queue.cloudflare import NativeMessage, QueueMessage
from application.persistence import PersistenceError
from application.quotations.use_cases import QuotationProcessor
from entrypoints.cloudflare.consumer import consume_batch
from entrypoints.cloudflare.runtime import (
    EventBindings,
    event_scope,
    get_cors_origins,
    get_database,
    get_environment,
    get_queue,
)


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
    CORS_ALLOWED_ORIGINS: str = ""


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

    async def test_cors_isolates_origins_and_preserves_preflight_and_error_responses(
        self,
    ) -> None:
        import httpx

        from application.lockers.ports import LockerRepository
        from composition import create_application

        first = Environment(Database(), Queue(), "https://first.example")
        second = Environment(Database(), Queue(), "https://second.example")
        entered = 0
        ready = asyncio.Event()

        async def unavailable(location_id: str | None = None) -> None:
            nonlocal entered
            environment = get_environment()
            entered += 1
            if entered == 2:
                ready.set()
            await asyncio.wait_for(ready.wait(), timeout=2)
            self.assertIs(get_environment(), environment)
            raise PersistenceError()

        lockers = AsyncMock(spec=LockerRepository)
        lockers.list_all.side_effect = unavailable
        application = create_application(
            AsyncMock(),
            AsyncMock(),
            lockers,
            AsyncMock(),
            AsyncMock(),
            cors_origins=get_cors_origins,
        )
        wrapped = EventBindings(application)

        async def invoke(environment: Environment) -> None:
            async def event(scope: Scope, receive: Receive, send: Send) -> None:
                scope["env"] = environment
                await wrapped(scope, receive, send)

            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=event), base_url="http://worker"
            ) as client:
                origin = environment.CORS_ALLOWED_ORIGINS
                preflight = await client.options(
                    "/quotations",
                    headers={
                        "Origin": origin,
                        "Access-Control-Request-Method": "POST",
                        "Access-Control-Request-Headers": "content-type",
                    },
                )
                self.assertEqual(preflight.status_code, 200)
                self.assertEqual(
                    preflight.headers["access-control-allow-origin"], origin
                )
                response = await client.get("/lockers", headers={"Origin": origin})
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json(), {"detail": "Persistence unavailable"})
                self.assertEqual(
                    response.headers["access-control-allow-origin"], origin
                )
                self.assertNotIn("access-control-allow-credentials", response.headers)
            with self.assertRaises(PersistenceError):
                get_environment()

        await asyncio.gather(invoke(first), invoke(second))

    async def test_invalid_event_cors_rejects_before_io_and_next_event_recovers(
        self,
    ) -> None:
        import httpx

        from composition import create_application

        @dataclass
        class ConfiguredEnvironment:
            DB: Database
            QUOTATIONS: Queue
            CORS_ALLOWED_ORIGINS: object

        database = Database()
        queue = AsyncMock(spec=Queue)
        environment = ConfiguredEnvironment(database, queue, "*")
        application = create_application(
            AsyncMock(),
            AsyncMock(),
            AsyncMock(),
            AsyncMock(),
            AsyncMock(),
            cors_origins=get_cors_origins,
        )
        handler = AsyncMock()

        @application.get("/probe")
        async def probe() -> dict[str, bool]:
            await handler()
            get_database().prepare("handler reached")
            await get_queue().send({"probe": "reached"})
            return {"ok": True}

        wrapped = EventBindings(application)

        async def event(scope: Scope, receive: Receive, send: Send) -> None:
            scope["env"] = environment
            await wrapped(scope, receive, send)

        allowed = "https://valid.example"
        with patch.dict("os.environ", {"CORS_ALLOWED_ORIGINS": allowed}):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=event), base_url="http://worker"
            ) as client:
                invalid_values: tuple[object, ...] = (
                    "https://valid.example/path",
                    "*",
                    123,
                )
                for invalid in invalid_values:
                    environment.CORS_ALLOWED_ORIGINS = invalid
                    for headers in ({}, {"Origin": allowed}):
                        with self.subTest(value=invalid, headers=headers):
                            with self.assertRaisesRegex(
                                ValueError, "CORS_ALLOWED_ORIGINS"
                            ):
                                await client.get("/probe", headers=headers)
                            handler.assert_not_awaited()
                            self.assertEqual(database.queries, [])
                            queue.send.assert_not_awaited()
                            with self.assertRaises(PersistenceError):
                                get_environment()
                environment.CORS_ALLOWED_ORIGINS = allowed
                response = await client.get("/probe", headers={"Origin": allowed})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json(), {"ok": True})
                self.assertEqual(
                    response.headers["access-control-allow-origin"], allowed
                )
                handler.assert_awaited_once()
                self.assertEqual(database.queries, ["handler reached"])
                queue.send.assert_awaited_once_with({"probe": "reached"})
                with self.assertRaises(PersistenceError):
                    get_environment()

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
import entrypoints.cloudflare.runtime as context
with patch.object(context,'get_database', side_effect=AssertionError('import DB access')), patch.object(context,'get_queue', side_effect=AssertionError('import queue access')):
    from entrypoints.cloudflare import api as cloudflare_api
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
        await worker.queue(batch, object(), object())
        assert consume.await_count == 2
        consume.assert_awaited_with(batch, environment, cloudflare_api.processor)
    events = []
    environment = types.SimpleNamespace(DB=object(), QUOTATIONS=object())
    worker.env = environment
    callback_environment = object()
    prior = object()
    class Message:
        def ack(self):
            assert context.get_environment() is environment
            events.append('ack')
            if outcome == 'ack-failure':
                raise OSError('ack failed')
        @property
        def body(self):
            events.append('body')
            return {'quotation_id':'00000000-0000-0000-0000-000000000001'}
    async def process(identifier):
        assert context.get_environment() is environment
        events.append('process')
        if outcome == 'process-failure':
            raise ValueError('processing failed')
    for complete in (False, True):
        for outcome in ('success', 'ack-failure', 'process-failure'):
            events.clear()
            message_batch = types.SimpleNamespace(messages=[Message()])
            with patch.object(cloudflare_api.processor, 'process', side_effect=process) as processing:
                with context.event_scope(prior):
                    try:
                        if complete:
                            await worker.queue(message_batch, callback_environment, object())
                        else:
                            await worker.queue(message_batch)
                    except (OSError, ValueError):
                        assert outcome != 'success'
                    else:
                        assert outcome == 'success'
                    assert context.get_environment() is prior
                assert events == (['ack'] if outcome == 'ack-failure' else ['ack','body','process'])
                assert processing.await_count == (0 if outcome == 'ack-failure' else 1)
            try:
                context.get_environment()
            except context.PersistenceError:
                pass
            else:
                raise AssertionError('event context leaked')
    assert cloudflare_api.app is application
    assert cloudflare_api.processor.repository is cloudflare_api.quotation_repository
asyncio.run(check_delegate())
from fastapi.testclient import TestClient
async def bound_request(scope, receive, send):
    scope['env'] = types.SimpleNamespace(CORS_ALLOWED_ORIGINS='https://worker.example')
    await cloudflare_api.event_app(scope, receive, send)
with TestClient(bound_request) as client:
    response = client.options('/quotations', headers={
        'Origin':'https://worker.example', 'Access-Control-Request-Method':'POST',
        'Access-Control-Request-Headers':'content-type'})
    assert response.status_code == 200, response.text
    assert response.headers['access-control-allow-origin'] == 'https://worker.example'
    assert 'access-control-allow-credentials' not in response.headers
for name in ('entrypoints.server.api','entrypoints.server.consumer','sqlmodel','asyncpg','alembic','aio_pika'):
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
from unittest.mock import AsyncMock, patch
from application.quotations.ports import QuotationRepository
from entrypoints.cloudflare.consumer import create_processor
repository = AsyncMock(spec=QuotationRepository)
clock = lambda: datetime.now(timezone.utc)
processor = create_processor(repository, clock)
assert processor.repository is repository
assert processor.clock is clock
assert repository.mock_calls == []
for name in ('composition', 'entrypoints.cloudflare.api', 'entrypoints.server.api',
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
