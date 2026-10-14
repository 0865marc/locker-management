from contextlib import asynccontextmanager

from fastapi import FastAPI

from adapters.database.connection import create_database, get_database_url
from adapters.database.sqlmodel_repositories import (
    SqlModelDeliveryRepository,
    SqlModelReturnRepository,
)
from adapters.http.routes import create_router
from application.use_cases import DeliveryService, ReturnService


def create_app(database_url: str | None = None) -> FastAPI:
    """Punto de composición: conecta adaptadores, servicios y recursos."""
    engine, sessions = create_database(database_url or get_database_url())
    delivery_service = DeliveryService(SqlModelDeliveryRepository(sessions))
    return_service = ReturnService(SqlModelReturnRepository(sessions))

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            yield
        finally:
            await engine.dispose()

    app = FastAPI(title="Delivery y Return · Arquitectura hexagonal", lifespan=lifespan)

    app.state.delivery_service = delivery_service
    app.state.return_service = return_service
    app.include_router(create_router(delivery_service, return_service))
    return app


app = create_app()
