from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException

from adapters.http.delivery_schemas import CreateDelivery, DeliveryResponse
from adapters.http.request_validation import require_empty_action_body
from adapters.http.locker_routes import capacity_http
from application.delivery_use_cases import DeliveryService
from application.errors import ParcelNotFoundError
from domain.lockers import CapacityConflictError, LockerNotFoundError
from domain.validation import CustodyConflictError
from domain.deliveries import Delivery


def create_delivery_router(delivery: DeliveryService) -> APIRouter:
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

    return router
