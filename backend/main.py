from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from adapters.database.connection import create_database, get_database_url
from adapters.database.sqlmodel_deliveries import SqlModelDeliveryRepository
from adapters.database.sqlmodel_returns import SqlModelReturnRepository
from adapters.http.delivery_routes import create_delivery_router
from adapters.http.return_routes import create_return_router
from adapters.database.sqlmodel_lockers import SqlModelLockerRepository
from adapters.http.locker_routes import create_locker_router
from application.locker_use_cases import LockerService
from application.delivery_use_cases import DeliveryService
from application.return_use_cases import ReturnService


def create_app(database_url: str | None = None) -> FastAPI:
    """Punto de composición: conecta adaptadores, servicios y recursos."""
    engine, sessions = create_database(database_url or get_database_url())
    delivery_service = DeliveryService(SqlModelDeliveryRepository(sessions))
    locker_service = LockerService(SqlModelLockerRepository(sessions))
    return_service = ReturnService(SqlModelReturnRepository(sessions))

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(title="Delivery y Return · Arquitectura hexagonal", lifespan=lifespan)

    app.state.locker_service = locker_service
    app.include_router(create_locker_router(locker_service))
    app.state.delivery_service = delivery_service
    app.state.return_service = return_service
    app.include_router(create_delivery_router(delivery_service))
    app.include_router(create_return_router(return_service))
    return app


app = create_app()
