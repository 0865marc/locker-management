"""Queues publication and synchronous acknowledgement before application work."""

from collections.abc import Callable, Mapping, Sequence
from typing import Protocol, TypeGuard
from uuid import UUID

from application.quotations.errors import PublicationError
from application.quotations.use_cases import QuotationProcessor


class QueueBinding(Protocol):
    async def send(self, body: dict[str, str]) -> None: ...


class QueueMessage(Protocol):
    @property
    def body(self) -> object: ...

    def ack(self) -> None: ...


class QueueBatch(Protocol):
    @property
    def messages(self) -> Sequence[QueueMessage]: ...


def _mapping(value: object) -> TypeGuard[Mapping[str, object]]:
    return isinstance(value, dict)


class CloudflareQuotationPublisher:
    def __init__(self, provider: Callable[[], QueueBinding]) -> None:
        self.provider = provider

    async def publish(self, quotation_id: UUID) -> None:
        try:
            await self.provider().send({"quotation_id": str(quotation_id)})
        except Exception as error:
            raise PublicationError("Quotation publication was not confirmed") from error


async def handle_message(message: QueueMessage, processor: QuotationProcessor) -> None:
    # Queues ack() is synchronous. A failed call must prevent even reading body.
    message.ack()
    payload = message.body
    if not _mapping(payload) or set(payload) != {"quotation_id"}:
        return
    identifier = payload["quotation_id"]
    if not isinstance(identifier, str):
        return
    try:
        quotation_id = UUID(identifier)
    except ValueError:
        return
    await processor.process(quotation_id)
