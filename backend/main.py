from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from adapters.database.connection import create_database, get_database_url
from adapters.database.sqlmodel_repositories import (
    SqlModelDeliveryRepository,
    SqlModelReturnRepository,
)
from adapters.http.routes import create_router
from adapters.database.sqlmodel_lockers import SqlModelLockerRepository
from adapters.http.locker_routes import create_locker_router
from application.locker_use_cases import LockerService
from application.use_cases import DeliveryService, ReturnService


def create_app(database_url: str | None = None) -> FastAPI:
    """Punto de composición: conecta adaptadores, servicios y recursos."""
    engine, sessions = create_database(database_url or get_database_url())
    delivery_service = DeliveryService(SqlModelDeliveryRepository(sessions))
    locker_service = LockerService(SqlModelLockerRepository(sessions))
    return_service = ReturnService(SqlModelReturnRepository(sessions))

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(title="Delivery y Return · Arquitectura hexagonal", lifespan=lifespan)

    app.state.locker_service = locker_service
    app.include_router(create_locker_router(locker_service))
    app.state.delivery_service = delivery_service
    app.state.return_service = return_service
    app.include_router(create_router(delivery_service, return_service))
    return app


app = create_app()
