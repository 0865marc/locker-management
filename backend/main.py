from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from adapters.database.connection import create_database, get_database_url
from adapters.database.sqlmodel_deliveries import SqlModelDeliveryRepository
from adapters.database.sqlmodel_lockers import SqlModelLockerRepository
from adapters.database.sqlmodel_quotations import SqlModelQuotationRepository
from adapters.database.sqlmodel_returns import SqlModelReturnRepository
from adapters.queue.rabbitmq import RabbitMQ, get_rabbitmq_url
from application.quotations.ports import QuotationPublisher
from composition import create_application
from composition import utc_now as utc_now


def create_app(
    database_url: str | None = None, *, publisher: QuotationPublisher | None = None
) -> FastAPI:
    """Punto de composición: conecta adaptadores, servicios y recursos."""
    engine, sessions = create_database(database_url or get_database_url())

    broker: RabbitMQ | None = None
    if publisher is None:
        broker = RabbitMQ(get_rabbitmq_url())
        publisher = broker

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        try:
            if broker is not None:
                await broker.open()
            yield
        finally:
            try:
                if broker is not None:
                    await broker.close()
            finally:
                await engine.dispose()

    return create_application(
        SqlModelDeliveryRepository(sessions),
        SqlModelReturnRepository(sessions),
        SqlModelLockerRepository(sessions),
        SqlModelQuotationRepository(sessions),
        publisher,
        clock=utc_now,
        lifespan=lifespan,
    )


app = create_app()
