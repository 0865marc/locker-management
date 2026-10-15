from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException

from adapters.http.return_schemas import CreateReturn, ReturnResponse
from adapters.http.request_validation import require_empty_action_body
from adapters.http.locker_routes import capacity_http
from application.return_use_cases import ReturnService
from application.errors import ParcelNotFoundError
from domain.lockers import CapacityConflictError, LockerNotFoundError
from domain.validation import CustodyConflictError
from domain.returns import Return


def create_return_router(returns: ReturnService) -> APIRouter:
    router = APIRouter()

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
