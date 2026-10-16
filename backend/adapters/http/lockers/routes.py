from collections.abc import Awaitable, Mapping, Sequence
from math import isfinite
from typing import Annotated, TypeGuard, TypeVar
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BeforeValidator

from adapters.http.lockers.schemas import (
    AddCompartments,
    AvailabilityResponse,
    CompartmentResponse,
    CreateLocker,
    LockerResponse,
    UpdateCompartment,
    UpdateLocker,
)
from application.lockers import LockerService
from domain.lockers import (
    Availability,
    CapacityConflictError,
    Compartment,
    Dimensions,
    Locker,
    LockerNotFoundError,
)


def capacity_http(error: CapacityConflictError) -> HTTPException:
    return HTTPException(
        status_code=409, detail={"code": error.code, "message": str(error)}
    )


T = TypeVar("T")


async def invoke(awaitable: Awaitable[T]) -> T:
    try:
        return await awaitable
    except LockerNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except CapacityConflictError as error:
        raise capacity_http(error) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error


def _query_integer(value: object) -> int:
    # URL query values are text, but decimal/exponent coercion must not accept floats.
    if isinstance(value, str) and value.isascii() and value.isdigit():
        return int(value)
    raise ValueError("Las dimensiones deben ser enteros positivos")


QueryInteger = Annotated[
    int, Query(ge=1, le=2147483647), BeforeValidator(_query_integer)
]


def is_object_mapping(value: object) -> TypeGuard[Mapping[object, object]]:
    # Every dictionary entry is an object; expose a read-only generic view.
    return isinstance(value, dict)


def is_object_list(value: object) -> TypeGuard[Sequence[object]]:
    # Keep the JSON-list check while exposing its elements as objects.
    return isinstance(value, list)


def contains_nonfinite(value: object) -> bool:
    if isinstance(value, float):
        return not isfinite(value)
    if is_object_mapping(value):
        return any(contains_nonfinite(child) for child in value.values())
    if is_object_list(value):
        return any(contains_nonfinite(child) for child in value)
    return False


async def require_finite_coordinates(request: Request) -> None:
    # Reject non-standard numeric tokens anywhere before Pydantic can echo them
    # in validation errors, which JSONResponse cannot encode as valid JSON.
    if not await request.body():
        return
    try:
        body: object = await request.json()
    except ValueError:
        # Required-body, malformed JSON and content-type validation remain FastAPI's.
        return
    if contains_nonfinite(body):
        raise HTTPException(
            status_code=422, detail="El cuerpo debe contener números JSON finitos"
        )


def create_locker_router(service: LockerService) -> APIRouter:
    router = APIRouter(prefix="/lockers", tags=["Locker"])

    @router.post(
        "",
        response_model=LockerResponse,
        status_code=201,
        dependencies=[Depends(require_finite_coordinates)],
    )
    async def create(body: CreateLocker) -> Locker:
        return await invoke(
            service.create(
                body.location_id,
                [b.domain() for b in body.compartments],
                body.active,
                body.address.domain() if body.address is not None else None,
                body.coordinates.domain() if body.coordinates is not None else None,
            )
        )

    @router.get("", response_model=list[LockerResponse])
    async def list_all(location_id: str | None = None) -> list[Locker]:
        return await invoke(service.list_all(location_id))

    @router.get("/availability", response_model=AvailabilityResponse)
    async def availability(
        location_id: str,
        width_mm: QueryInteger,
        height_mm: QueryInteger,
        depth_mm: QueryInteger,
    ) -> Availability:
        return await invoke(
            service.availability(location_id, Dimensions(width_mm, height_mm, depth_mm))
        )

    @router.get("/{id}", response_model=LockerResponse)
    async def get(id: UUID) -> Locker:
        return await invoke(service.get_by_id(id))

    @router.patch(
        "/{id}",
        response_model=LockerResponse,
        dependencies=[Depends(require_finite_coordinates)],
    )
    async def update(id: UUID, body: UpdateLocker) -> Locker:
        return await invoke(service.update(id, body.domain()))

    @router.post("/{id}/compartments", response_model=LockerResponse, status_code=201)
    async def add(id: UUID, body: AddCompartments) -> Locker:
        return await invoke(
            service.add_compartments(id, [b.domain() for b in body.compartments])
        )

    @router.patch("/{id}/compartments/{cell_id}", response_model=CompartmentResponse)
    async def change(id: UUID, cell_id: UUID, body: UpdateCompartment) -> Compartment:
        return await invoke(
            service.update_compartment(
                id,
                cell_id,
                body.dimensions.domain() if body.dimensions else None,
                body.enabled,
            )
        )

    @router.delete("/{id}/compartments/{cell_id}", status_code=204)
    async def retire(id: UUID, cell_id: UUID) -> Response:
        await invoke(service.retire_compartment(id, cell_id))
        return Response(status_code=204)

    return router
