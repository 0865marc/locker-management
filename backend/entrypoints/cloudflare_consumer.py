"""Queue composition and event handling, independent of HTTP and the SDK."""

from collections.abc import Callable
from datetime import datetime

from adapters.providers.simulated_shipping import (
    SimulatedEconomyProvider,
    SimulatedExpressProvider,
    SimulatedStandardProvider,
)
from adapters.queue.cloudflare import NativeMessage, QueueBatch, handle_message
from adapters.runtime.cloudflare import WorkerEnvironment, event_scope
from application.quotations.comparison import ShippingQuoteComparator
from application.quotations.ports import QuotationRepository
from application.quotations.use_cases import QuotationProcessor


def create_processor(
    repository: QuotationRepository, clock: Callable[[], datetime]
) -> QuotationProcessor:
    return QuotationProcessor(
        repository,
        ShippingQuoteComparator(
            (
                SimulatedEconomyProvider(),
                SimulatedStandardProvider(),
                SimulatedExpressProvider(),
            )
        ),
        clock,
    )


async def consume_batch(
    batch: QueueBatch, environment: WorkerEnvironment, processor: QuotationProcessor
) -> None:
    with event_scope(environment):
        for message in batch.messages:
            await handle_message(NativeMessage(message), processor)
