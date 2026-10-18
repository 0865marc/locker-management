from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI

from adapters.database.connection import create_database, get_database_url
from adapters.database.sqlmodel_deliveries import SqlModelDeliveryRepository
from adapters.database.sqlmodel_lockers import SqlModelLockerRepository
from adapters.database.sqlmodel_quotations import SqlModelQuotationRepository
from adapters.database.sqlmodel_returns import SqlModelReturnRepository
from adapters.http.cors import ScopedCORSMiddleware, get_cors_allowed_origins
from adapters.http.routes import create_router
from adapters.queue.rabbitmq import RabbitMQ, get_rabbitmq_url
from application.deliveries.use_cases import DeliveryService
from application.lockers.use_cases import LockerService
from application.quotations.ports import QuotationPublisher
from application.quotations.use_cases import QuotationService
from application.returns.use_cases import ReturnService
from application.tracking.use_cases import TrackingService


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_app(
    database_url: str | None = None, *, publisher: QuotationPublisher | None = None
) -> FastAPI:
    """Punto de composición: conecta adaptadores, servicios y recursos."""
    cors_allowed_origins = get_cors_allowed_origins()
    engine, sessions = create_database(database_url or get_database_url())
    delivery_repository = SqlModelDeliveryRepository(sessions)
    locker_repository = SqlModelLockerRepository(sessions)
    return_repository = SqlModelReturnRepository(sessions)
    delivery_service = DeliveryService(delivery_repository, utc_now)
    locker_service = LockerService(locker_repository)
    return_service = ReturnService(return_repository, utc_now)
    tracking_service = TrackingService(
        delivery_repository, return_repository, locker_repository
    )

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
    app.add_middleware(
        ScopedCORSMiddleware,
        allow_origins=cors_allowed_origins,
    )

    app.state.quotation_service = quotation_service
    app.state.locker_service = locker_service
    app.state.delivery_service = delivery_service
    app.state.return_service = return_service
    app.state.tracking_service = tracking_service
    app.include_router(
        create_router(
            delivery_service,
            return_service,
            locker_service,
            quotation_service,
            tracking_service,
        )
    )
    return app


app = create_app()
