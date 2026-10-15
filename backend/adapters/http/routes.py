import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from adapters.http.schemas import (
    CreateDelivery,
    CreateReturn,
    DeliveryResponse,
    ReturnResponse,
)
from application.use_cases import DeliveryService, ParcelNotFoundError, ReturnService
from domain.lockers import CapacityConflictError, LockerNotFoundError
from adapters.http.locker_routes import capacity_http
from domain.models import CustodyConflictError, Delivery, Return


async def require_empty_action_body(request: Request) -> None:
    """Las salidas solo aceptan ausencia de cuerpo o un objeto JSON vacío."""
    raw_body = await request.body()
    if not raw_body:
        return
    try:
        body = json.loads(raw_body)
    except (ValueError, UnicodeDecodeError) as error:
        raise HTTPException(status_code=422, detail="El cuerpo debe ser {} o estar ausente") from error
    if not isinstance(body, dict) or body:
        raise HTTPException(status_code=422, detail="El cuerpo debe ser {} o estar ausente")


def create_router(delivery: DeliveryService, returns: ReturnService) -> APIRouter:
    """Adaptador HTTP que invoca los casos de uso de los servicios recibidos."""
    router = APIRouter()

    @router.post("/deliveries", response_model=DeliveryResponse, status_code=201, tags=["Delivery"])
    async def create_delivery(body: CreateDelivery) -> Delivery:
        try:
            return await delivery.create(
                tracking_number=body.tracking_number, carrier_code=body.carrier_code,
                recipient_name=body.recipient_name, recipient_phone=body.recipient_phone,
                pickup_deadline_at=body.pickup_deadline_at, locker_id=body.locker_id,
                parcel_dimensions=body.parcel_dimensions.domain() if body.parcel_dimensions is not None else None)
        except LockerNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except CapacityConflictError as error:
            raise capacity_http(error) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.get("/deliveries", response_model=list[DeliveryResponse], tags=["Delivery"])
    async def list_deliveries() -> list[Delivery]:
        return await delivery.list_all()

    @router.post("/deliveries/{id}/collect", response_model=DeliveryResponse,
                 dependencies=[Depends(require_empty_action_body)], tags=["Delivery"])
    async def collect_delivery(id: UUID) -> Delivery:
        try:
            return await delivery.collect(id)
        except ParcelNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except CustodyConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @router.post("/deliveries/{id}/return-to-carrier", response_model=DeliveryResponse,
                 dependencies=[Depends(require_empty_action_body)], tags=["Delivery"])
    async def return_delivery_to_carrier(id: UUID) -> Delivery:
        try:
            return await delivery.return_to_carrier(id)
        except ParcelNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except CustodyConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @router.post("/returns", response_model=ReturnResponse, status_code=201, tags=["Return"])
    async def create_return(body: CreateReturn) -> Return:
        try:
            return await returns.create(tracking_number=body.tracking_number,
                carrier_code=body.carrier_code, sender_name=body.sender_name, locker_id=body.locker_id,
                parcel_dimensions=body.parcel_dimensions.domain() if body.parcel_dimensions is not None else None)
        except LockerNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except CapacityConflictError as error:
            raise capacity_http(error) from error
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    @router.get("/returns", response_model=list[ReturnResponse], tags=["Return"])
    async def list_returns() -> list[Return]:
        return await returns.list_all()

    @router.post("/returns/{id}/hand-over", response_model=ReturnResponse,
                 dependencies=[Depends(require_empty_action_body)], tags=["Return"])
    async def hand_over_return(id: UUID) -> Return:
        try:
            return await returns.hand_over(id)
        except ParcelNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except CustodyConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    return router
