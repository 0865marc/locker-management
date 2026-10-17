"""Workers composition: one HTTP app, bindings resolved only inside each event."""

from typing import cast

from pyodide.ffi import JsException
from workers import Request, WorkerEntrypoint, asgi

from adapters.database.d1.deliveries import D1DeliveryRepository
from adapters.database.d1.lockers import D1LockerRepository
from adapters.database.d1.native import NativeDatabase
from adapters.database.d1.quotations import D1QuotationRepository
from adapters.database.d1.returns import D1ReturnRepository
from adapters.providers.simulated_shipping import (
    SimulatedEconomyProvider,
    SimulatedExpressProvider,
    SimulatedStandardProvider,
)
from adapters.queue.cloudflare import (
    CloudflareQuotationPublisher,
    NativeMessage,
    QueueBatch,
    handle_message,
)
from adapters.runtime.cloudflare import (
    EventBindings,
    WorkerEnvironment,
    event_scope,
    get_database,
    get_queue,
)
from application.quotations.comparison import ShippingQuoteComparator
from application.quotations.use_cases import QuotationProcessor
from composition import create_application, utc_now


def native_database() -> NativeDatabase:
    return NativeDatabase(get_database(), (JsException, OSError))


quotation_repository = D1QuotationRepository(native_database)
app = create_application(
    D1DeliveryRepository(native_database),
    D1ReturnRepository(native_database),
    D1LockerRepository(native_database),
    quotation_repository,
    CloudflareQuotationPublisher(get_queue),
)
event_app = EventBindings(app)
processor = QuotationProcessor(
    quotation_repository,
    ShippingQuoteComparator(
        (
            SimulatedEconomyProvider(),
            SimulatedStandardProvider(),
            SimulatedExpressProvider(),
        )
    ),
    utc_now,
)


class Default(WorkerEntrypoint):
    async def fetch(self, request: Request) -> object:
        return await asgi.fetch(event_app, request, self.env, self.ctx)

    async def queue(self, batch: QueueBatch) -> None:
        with event_scope(cast(WorkerEnvironment, self.env)):
            for message in batch.messages:
                await handle_message(NativeMessage(message), processor)
