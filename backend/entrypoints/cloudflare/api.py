"""Workers composition: one HTTP app, bindings resolved only inside each event."""

from typing import cast

from pyodide.ffi import JsException
from workers import Request, WorkerEntrypoint, asgi

from adapters.database.d1.deliveries import D1DeliveryRepository
from adapters.database.d1.lockers import D1LockerRepository
from adapters.database.d1.native import NativeDatabase
from adapters.database.d1.quotations import D1QuotationRepository
from adapters.database.d1.returns import D1ReturnRepository
from adapters.queue.cloudflare import CloudflareQuotationPublisher, QueueBatch
from composition import create_application, utc_now
from entrypoints.cloudflare.consumer import consume_batch, create_processor
from entrypoints.cloudflare.runtime import (
    EventBindings,
    WorkerEnvironment,
    get_cors_origins,
    get_database,
    get_queue,
)


def native_database() -> NativeDatabase:
    return NativeDatabase(get_database(), (JsException, OSError))


quotation_repository = D1QuotationRepository(native_database)
app = create_application(
    D1DeliveryRepository(native_database),
    D1ReturnRepository(native_database),
    D1LockerRepository(native_database),
    quotation_repository,
    CloudflareQuotationPublisher(get_queue),
    cors_origins=get_cors_origins,
)
event_app = EventBindings(app)
processor = create_processor(quotation_repository, utc_now)


class Default(WorkerEntrypoint):
    async def fetch(self, request: Request) -> object:
        return await asgi.fetch(event_app, request, self.env, self.ctx)

    async def queue(self, batch: QueueBatch) -> None:
        await consume_batch(batch, cast(WorkerEnvironment, self.env), processor)
