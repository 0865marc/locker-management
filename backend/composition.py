"""Shared HTTP composition; infrastructure is supplied through application ports."""

from collections.abc import Callable
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.types import Lifespan

from adapters.http.routes import create_router
from application.deliveries.ports import DeliveryRepository
from application.deliveries.use_cases import DeliveryService
from application.lockers.ports import LockerRepository
from application.lockers.use_cases import LockerService
from application.persistence import PersistenceError
from application.quotations.ports import QuotationPublisher, QuotationRepository
from application.quotations.use_cases import QuotationService
from application.returns.ports import ReturnRepository
from application.returns.use_cases import ReturnService


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def persistence_unavailable(request: Request, error: Exception) -> JSONResponse:
    """Do not expose storage errors, SQL or event bindings in public responses."""
    return JSONResponse(status_code=503, content={"detail": "Persistence unavailable"})


def create_application(
    deliveries: DeliveryRepository,
    returns: ReturnRepository,
    lockers: LockerRepository,
    quotations: QuotationRepository,
    publisher: QuotationPublisher,
    *,
    clock: Callable[[], datetime] = utc_now,
    lifespan: Lifespan[FastAPI] | None = None,
) -> FastAPI:
    delivery_service = DeliveryService(deliveries, clock)
    return_service = ReturnService(returns, clock)
    locker_service = LockerService(lockers)
    quotation_service = QuotationService(quotations, publisher, clock)
    app = FastAPI(title="Locker Management Demo", lifespan=lifespan)
    app.add_exception_handler(PersistenceError, persistence_unavailable)
    app.state.delivery_service = delivery_service
    app.state.return_service = return_service
    app.state.locker_service = locker_service
    app.state.quotation_service = quotation_service
    app.include_router(
        create_router(
            delivery_service, return_service, locker_service, quotation_service
        )
    )
    return app
