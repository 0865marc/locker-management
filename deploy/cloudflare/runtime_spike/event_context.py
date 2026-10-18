"""Event binding scope and direct checks that run in the same asyncio task."""

import asyncio
from contextvars import Context, ContextVar
from dataclasses import dataclass
from typing import cast

from bindings import Database, Environment, Queue
from starlette.types import ASGIApp, Message, Receive, Scope, Send

current_environment: ContextVar[Environment] = ContextVar("spike_environment")


class EventContext:
    def __init__(self, application: ASGIApp) -> None:
        self.application = application

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.application(scope, receive, send)
            return
        token = current_environment.set(cast(Environment, scope["env"]))
        try:
            await self.application(scope, receive, send)
        finally:
            current_environment.reset(token)


@dataclass
class ProbeEnvironment:
    DB: Database
    QUOTATIONS: Queue
    LABEL: str


async def verify_context_cleanup(environment: Environment) -> None:
    """Assert reset after success/error with both a prior value and no value.

    Unlike checking after asgi.fetch's child task, these assertions observe the
    exact task that invoked EventContext and fail when reset(token) is removed.
    """
    inner = ProbeEnvironment(environment.DB, environment.QUOTATIONS, "direct-inner")

    async def receive() -> Message:
        return {"type": "http.request", "body": b""}

    async def send(message: Message) -> None:
        assert message["type"] == "http.response.start"

    async def application(scope: Scope, receive: Receive, send: Send) -> None:
        assert current_environment.get() is inner
        await asyncio.sleep(0)
        if scope["path"] == "/fail":
            raise ValueError("intentional same-task cleanup probe")
        await send({"type": "http.response.start", "status": 200})

    wrapped = EventContext(application)

    async def exercise() -> None:
        for path in ("/ok", "/fail"):
            before = current_environment.get(None)
            try:
                await wrapped(
                    {"type": "http", "path": path, "env": inner}, receive, send
                )
            except ValueError:
                assert path == "/fail"
            else:
                assert path == "/ok"
            assert current_environment.get(None) is before
            if before is None:
                try:
                    current_environment.get()
                except LookupError:
                    pass
                else:
                    raise AssertionError("ContextVar retained the event binding")

    previous = current_environment.set(environment)
    try:
        await exercise()
    finally:
        current_environment.reset(previous)
    # Explicitly empty Context prevents inheriting the outer event binding.
    await asyncio.create_task(exercise(), context=Context())
