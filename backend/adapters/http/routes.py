from fastapi import APIRouter

from adapters.http.deliveries.routes import create_delivery_router
from adapters.http.lockers.routes import create_locker_router
from adapters.http.quotations.routes import create_quotation_router
from adapters.http.returns.routes import create_return_router
from application.deliveries import DeliveryService
from application.lockers import LockerService
from application.quotations import QuotationService
from application.returns import ReturnService


def create_router(
    delivery_service: DeliveryService,
    return_service: ReturnService,
    locker_service: LockerService,
    quotation_service: QuotationService | None = None,
) -> APIRouter:
    router = APIRouter()
    router.include_router(create_locker_router(locker_service))
    router.include_router(create_delivery_router(delivery_service))
    router.include_router(create_return_router(return_service))
    if quotation_service is not None:
        router.include_router(create_quotation_router(quotation_service))
    return router
