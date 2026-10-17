"""Decode a raw message body only after the application requests its ack."""

from typing import Protocol, TypeGuard, cast

from adapters.queue.cloudflare import QueueMessage


class Convertible(Protocol):
    def to_py(self) -> object: ...


def python_mapping(value: object) -> TypeGuard[dict[object, object]]:
    return isinstance(value, dict)


class NativeMessage:
    def __init__(self, message: QueueMessage) -> None:
        self.message = message

    def ack(self) -> None:
        self.message.ack()

    @property
    def body(self) -> object:
        value = self.message.body
        if python_mapping(value):
            return value
        if hasattr(value, "to_py"):
            return cast(Convertible, value).to_py()
        return value
