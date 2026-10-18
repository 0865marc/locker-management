from uuid import UUID

from fastapi import APIRouter, HTTPException

from adapters.http.tracking.schemas import TrackingResponse
from application.tracking.models import TrackedParcel
from application.tracking.use_cases import (
    TrackingConflictError,
    TrackingNotFoundError,
    TrackingService,
)


def create_tracking_router(service: TrackingService) -> APIRouter:
    router = APIRouter(prefix="/tracking", tags=["tracking"])

    @router.get("/{id}", response_model=TrackingResponse)
    async def locate(id: UUID) -> TrackedParcel:
        try:
            return await service.get_by_id(id)
        except TrackingNotFoundError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        except TrackingConflictError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    return router
