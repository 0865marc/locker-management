from fastapi import APIRouter, HTTPException

from adapters.http.schemas import (
    CreateDelivery,
    CreateReturn,
    DeliveryResponse,
    ReturnResponse,
)
from application.use_cases import DeliveryService, ReturnService
from domain.models import Delivery, Return


def create_router(delivery: DeliveryService, returns: ReturnService) -> APIRouter:
    """Adaptador HTTP que invoca los casos de uso de los servicios recibidos."""
    router = APIRouter()

    @router.post("/deliveries", response_model=DeliveryResponse, status_code=201, tags=["Delivery"])
    async def create_delivery(body: CreateDelivery) -> Delivery:
        try:
            return await delivery.create(body.address)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.get("/deliveries", response_model=list[DeliveryResponse], tags=["Delivery"])
    async def list_deliveries() -> list[Delivery]:
        return await delivery.list_all()

    @router.post("/returns", response_model=ReturnResponse, status_code=201, tags=["Return"])
    async def create_return(body: CreateReturn) -> Return:
        try:
            return await returns.create(body.reason)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.get("/returns", response_model=list[ReturnResponse], tags=["Return"])
    async def list_returns() -> list[Return]:
        return await returns.list_all()

    return router
