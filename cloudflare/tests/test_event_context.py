"""CPython checks only for ContextVar cleanup; native ASGI remains separate."""

import unittest
from collections.abc import Sequence

from bindings import Statement
from event_context import ProbeEnvironment, verify_context_cleanup


class UnusedDatabase:
    def prepare(self, query: str) -> Statement:
        raise AssertionError("Binding must not be used in the scope cleanup probe")

    async def batch(self, statements: Sequence[Statement]) -> list[dict[str, object]]:
        raise AssertionError("Binding must not be used in the scope cleanup probe")


class UnusedQueue:
    async def send(self, body: dict[str, str]) -> None:
        raise AssertionError("Binding must not be used in the scope cleanup probe")


class ContextCleanupTests(unittest.IsolatedAsyncioTestCase):
    async def test_same_task_cleanup_after_success_and_exception(self) -> None:
        environment = ProbeEnvironment(UnusedDatabase(), UnusedQueue(), "outer")
        await verify_context_cleanup(environment)


if __name__ == "__main__":
    unittest.main()
