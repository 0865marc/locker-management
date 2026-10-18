"""Narrow structural boundary for the SDK's automatically converted bindings.

No runtime SDK objects are imported or accessed here. Native smoke tests verify
these method shapes; values crossing this boundary are checked before use.
"""

from collections.abc import Sequence
from typing import Protocol


class Statement(Protocol):
    def bind(self, *values: str | int | float | None) -> "Statement": ...

    async def first(self) -> dict[str, object] | None: ...

    async def run(self) -> dict[str, object]: ...


class Database(Protocol):
    def prepare(self, query: str) -> Statement: ...

    async def batch(
        self, statements: Sequence[Statement]
    ) -> list[dict[str, object]]: ...


class Queue(Protocol):
    async def send(self, body: dict[str, str]) -> None: ...


class Environment(Protocol):
    DB: Database
    QUOTATIONS: Queue
    LABEL: str


class Message(Protocol):
    id: str

    @property
    def body(self) -> object: ...

    def ack(self) -> None: ...


class MessageBatch(Protocol):
    messages: Sequence[Message]


class NativeResponse(Protocol):
    status: int

    async def text(self) -> str: ...
