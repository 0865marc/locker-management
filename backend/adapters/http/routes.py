from fastapi import APIRouter

from application.deliveries import DeliveryService
from application.returns import ReturnService
from application.lockers import LockerService
from adapters.http.deliveries.routes import create_delivery_router
from adapters.http.returns.routes import create_return_router
from adapters.http.lockers.routes import create_locker_router


def create_router(delivery_service: DeliveryService, return_service: ReturnService,
                  locker_service: LockerService) -> APIRouter:
    router = APIRouter()
    router.include_router(create_locker_router(locker_service))
    router.include_router(create_delivery_router(delivery_service))
    router.include_router(create_return_router(return_service))
    return router
