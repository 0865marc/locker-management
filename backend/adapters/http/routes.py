from fastapi import APIRouter

from adapters.http.deliveries.routes import create_delivery_router
from adapters.http.lockers.routes import create_locker_router
from adapters.http.quotations.routes import create_quotation_router
from adapters.http.returns.routes import create_return_router
from adapters.http.tracking.routes import create_tracking_router
from application.deliveries.use_cases import DeliveryService
from application.lockers.use_cases import LockerService
from application.quotations.use_cases import QuotationService
from application.returns.use_cases import ReturnService
from application.tracking.use_cases import TrackingService


def create_router(
    delivery_service: DeliveryService,
    return_service: ReturnService,
    locker_service: LockerService,
    quotation_service: QuotationService | None = None,
    tracking_service: TrackingService | None = None,
) -> APIRouter:
    router = APIRouter()
    router.include_router(create_locker_router(locker_service))
    router.include_router(create_delivery_router(delivery_service))
    router.include_router(create_return_router(return_service))
    if quotation_service is not None:
        router.include_router(create_quotation_router(quotation_service))
    if tracking_service is not None:
        router.include_router(create_tracking_router(tracking_service))
    return router
