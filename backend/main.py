from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI

from adapters.database.connection import create_database, get_database_url
from adapters.database.sqlmodel_deliveries import SqlModelDeliveryRepository
from adapters.database.sqlmodel_lockers import SqlModelLockerRepository
from adapters.database.sqlmodel_quotations import SqlModelQuotationRepository
from adapters.database.sqlmodel_returns import SqlModelReturnRepository
from adapters.http.routes import create_router
from adapters.queue.rabbitmq import RabbitMQ, get_rabbitmq_url
from application.deliveries.use_cases import DeliveryService
from application.lockers.use_cases import LockerService
from application.quotations.ports import QuotationPublisher
from application.quotations.use_cases import QuotationService
from application.returns.use_cases import ReturnService


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_app(
    database_url: str | None = None, *, publisher: QuotationPublisher | None = None
) -> FastAPI:
    """Punto de composición: conecta adaptadores, servicios y recursos."""
    engine, sessions = create_database(database_url or get_database_url())
    delivery_service = DeliveryService(SqlModelDeliveryRepository(sessions), utc_now)
    locker_service = LockerService(SqlModelLockerRepository(sessions))
    return_service = ReturnService(SqlModelReturnRepository(sessions), utc_now)

    broker: RabbitMQ | None = None
    if publisher is None:
        broker = RabbitMQ(get_rabbitmq_url())
        publisher = broker
    quotation_service = QuotationService(
        SqlModelQuotationRepository(sessions), publisher, utc_now
    )

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

    app = FastAPI(title="Locker Management Demo", lifespan=lifespan)

    app.state.quotation_service = quotation_service
    app.state.locker_service = locker_service
    app.state.delivery_service = delivery_service
    app.state.return_service = return_service
    app.include_router(
        create_router(
            delivery_service, return_service, locker_service, quotation_service
        )
    )
    return app


app = create_app()
