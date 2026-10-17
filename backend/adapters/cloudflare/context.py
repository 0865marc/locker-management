"""Resolve infrastructure from the current event without capturing bindings."""

from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Protocol, cast

from starlette.types import ASGIApp, Receive, Scope, Send

from adapters.database.d1.bindings import D1Database
from adapters.queue.cloudflare import QueueBinding
from application.persistence import PersistenceError


class WorkerEnvironment(Protocol):
    @property
    def DB(self) -> D1Database: ...

    @property
    def QUOTATIONS(self) -> QueueBinding: ...


_environment: ContextVar[WorkerEnvironment] = ContextVar("cloudflare_environment")


@contextmanager
def event_scope(environment: WorkerEnvironment) -> Generator[None]:
    token = _environment.set(environment)
    try:
        yield
    finally:
        _environment.reset(token)


def get_environment() -> WorkerEnvironment:
    try:
        return _environment.get()
    except LookupError as error:
        raise PersistenceError() from error


def get_database() -> D1Database:
    return get_environment().DB


def get_queue() -> QueueBinding:
    return get_environment().QUOTATIONS


class EventBindings:
    def __init__(self, application: ASGIApp) -> None:
        self.application = application

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.application(scope, receive, send)
            return
        with event_scope(cast(WorkerEnvironment, scope["env"])):
            await self.application(scope, receive, send)
