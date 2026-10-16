from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI

from adapters.database.connection import create_database, get_database_url
from adapters.database.sqlmodel_deliveries import SqlModelDeliveryRepository
from adapters.database.sqlmodel_returns import SqlModelReturnRepository
from adapters.database.sqlmodel_lockers import SqlModelLockerRepository
from adapters.http.routes import create_router
from application.lockers import LockerService
from application.deliveries import DeliveryService
from application.returns import ReturnService


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_app(database_url: str | None = None) -> FastAPI:
    """Punto de composición: conecta adaptadores, servicios y recursos."""
    engine, sessions = create_database(database_url or get_database_url())
    delivery_service = DeliveryService(SqlModelDeliveryRepository(sessions), utc_now)
    locker_service = LockerService(SqlModelLockerRepository(sessions))
    return_service = ReturnService(SqlModelReturnRepository(sessions), utc_now)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(title="Delivery y Return · Arquitectura hexagonal", lifespan=lifespan)

    app.state.locker_service = locker_service
    app.state.delivery_service = delivery_service
    app.state.return_service = return_service
    app.include_router(create_router(delivery_service, return_service, locker_service))
    return app


app = create_app()
