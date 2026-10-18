"""Validated, SDK-independent boundary for the native D1 binding.

The Workers bridge must normalize JS proxies and raise D1BindingError on binding
failures. Domain code never receives JS numbers or exception text.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol, TypeAlias

D1Value: TypeAlias = str | int | float | None
D1Row: TypeAlias = dict[str, D1Value]


class D1BindingError(RuntimeError):
    """An execution/transport failure, including an unknown commit outcome."""


@dataclass(frozen=True)
class D1Result:
    results: tuple[D1Row, ...] = ()
    changes: int = 0


class D1PreparedStatement(Protocol):
    def bind(self, *values: D1Value) -> "D1PreparedStatement": ...
    async def first(self) -> object: ...
    async def all(self) -> object: ...
    async def run(self) -> object: ...


class D1Database(Protocol):
    def prepare(self, sql: str, /) -> D1PreparedStatement: ...
    async def batch(self, statements: Sequence[D1PreparedStatement], /) -> object: ...


D1Provider: TypeAlias = Callable[[], D1Database]
