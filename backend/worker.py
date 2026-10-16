"""One sequential worker; consumed work has no automatic recovery."""
import asyncio
from contextlib import AsyncExitStack
from datetime import datetime, timezone
import os
import signal

from adapters.database.connection import create_database, get_database_url
from adapters.database.sqlmodel_quotations import SqlModelQuotationRepository
from adapters.providers.simulated_shipping import (
    SimulationProfile, SimulatedEconomyProvider, SimulatedStandardProvider, SimulatedExpressProvider,
)
from adapters.queue.rabbitmq import RabbitMQ, get_rabbitmq_url
from application.quotations import QuotationProcessor
from application.shipping_quotes import ShippingQuoteService


def simulation_profile() -> SimulationProfile:
    return SimulationProfile(
        delay_min_seconds=float(os.getenv('SHIPPING_DELAY_MIN_SECONDS', '0.05')),
        delay_max_seconds=float(os.getenv('SHIPPING_DELAY_MAX_SECONDS', '0.5')),
        no_response_probability=float(os.getenv('SHIPPING_NO_RESPONSE_PROBABILITY', '0.05')),
        error_probability=float(os.getenv('SHIPPING_ERROR_PROBABILITY', '0.10')))


async def run_worker() -> None:
    profile = simulation_profile()
    async with AsyncExitStack() as resources:
        engine, sessions = create_database(get_database_url())
        resources.push_async_callback(engine.dispose)
        broker = RabbitMQ(get_rabbitmq_url())
        resources.push_async_callback(broker.close)
        await broker.open()
        comparator = ShippingQuoteService((SimulatedEconomyProvider(profile),
            SimulatedStandardProvider(profile), SimulatedExpressProvider(profile)))
        processor = QuotationProcessor(SqlModelQuotationRepository(sessions), comparator,
                                       lambda: datetime.now(timezone.utc))
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


if __name__ == '__main__':
    asyncio.run(main())
