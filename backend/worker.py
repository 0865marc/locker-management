"""One sequential worker; consumed work has no automatic recovery."""

import asyncio
import signal
from contextlib import AsyncExitStack
from datetime import datetime, timezone

from adapters.database.connection import create_database, get_database_url
from adapters.database.sqlmodel_quotations import SqlModelQuotationRepository
from adapters.providers.simulated_shipping import (
    SimulatedEconomyProvider,
    SimulatedExpressProvider,
    SimulatedStandardProvider,
)
from adapters.queue.rabbitmq import RabbitMQ, get_rabbitmq_url
from application.quotations.comparison import ShippingQuoteComparator
from application.quotations.use_cases import QuotationProcessor


async def run_worker() -> None:
    async with AsyncExitStack() as resources:
        engine, sessions = create_database(get_database_url())
        resources.push_async_callback(engine.dispose)
        broker = RabbitMQ(get_rabbitmq_url())
        resources.push_async_callback(broker.close)
        await broker.open()
        comparator = ShippingQuoteComparator(
            (
                SimulatedEconomyProvider(),
                SimulatedStandardProvider(),
                SimulatedExpressProvider(),
            )
        )
        processor = QuotationProcessor(
            SqlModelQuotationRepository(sessions),
            comparator,
            lambda: datetime.now(timezone.utc),
        )
        await broker.consume(processor)


async def main() -> None:
    task = asyncio.create_task(run_worker())
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signum, task.cancel)
    try:
        await task
    except asyncio.CancelledError:
        pass
    finally:
        for signum in (signal.SIGINT, signal.SIGTERM):
            loop.remove_signal_handler(signum)


if __name__ == "__main__":
    asyncio.run(main())
