"""Subset of workers.asgi.fetch used by the experiment."""

from typing import Protocol

from starlette.types import ASGIApp

from . import Context, Request

class Response(Protocol):
    status: int

    async def text(self) -> str: ...

async def fetch(
    app: ASGIApp, req: Request, env: object, ctx: Context | None = None
) -> Response: ...
