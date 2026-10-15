from uuid import UUID
from typing import Annotated
from pydantic import BeforeValidator
from fastapi import APIRouter, HTTPException, Query, Response
from domain.lockers import CapacityConflictError, Dimensions, LockerNotFoundError
from adapters.http.locker_schemas import AddCompartments, AvailabilityResponse, CompartmentResponse, CreateLocker, LockerResponse, UpdateCompartment, UpdateLocker

def capacity_http(error):
    return HTTPException(status_code=409, detail={'code': error.code, 'message': str(error)})

async def invoke(awaitable):
    try:
        return await awaitable
    except LockerNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except CapacityConflictError as error:
        raise capacity_http(error) from error
    except ValueError as error:
        raise HTTPException(status_code=422, detail=str(error)) from error

def _query_integer(value):
    # URL query values are text, but decimal/exponent coercion must not accept floats.
    if isinstance(value, str) and value.isascii() and value.isdigit():
        return int(value)
    raise ValueError('Las dimensiones deben ser enteros positivos')


QueryInteger = Annotated[int, Query(ge=1, le=2147483647), BeforeValidator(_query_integer)]


def create_locker_router(service):
    router = APIRouter(prefix='/lockers', tags=['Locker'])
    @router.post('', response_model=LockerResponse, status_code=201)
    async def create(body: CreateLocker):
        return await invoke(service.create(body.location_id, [b.domain() for b in body.compartments], body.active))
    @router.get('', response_model=list[LockerResponse])
    async def list_all(location_id: str | None = None):
        return await invoke(service.list_all(location_id))
    @router.get('/availability', response_model=AvailabilityResponse)
    async def availability(location_id: str, width_mm: QueryInteger, height_mm: QueryInteger, depth_mm: QueryInteger):
        return await invoke(service.availability(location_id, Dimensions(width_mm, height_mm, depth_mm)))
    @router.get('/{id}', response_model=LockerResponse)
    async def get(id: UUID):
        return await invoke(service.get_by_id(id))
    @router.patch('/{id}', response_model=LockerResponse)
    async def update(id: UUID, body: UpdateLocker):
        return await invoke(service.set_active(id, body.active))
    @router.post('/{id}/compartments', response_model=LockerResponse, status_code=201)
    async def add(id: UUID, body: AddCompartments):
        return await invoke(service.add_compartments(id, [b.domain() for b in body.compartments]))
    @router.patch('/{id}/compartments/{cell_id}', response_model=CompartmentResponse)
    async def change(id: UUID, cell_id: UUID, body: UpdateCompartment):
        return await invoke(service.update_compartment(id, cell_id, body.dimensions.domain() if body.dimensions else None, body.enabled))
    @router.delete('/{id}/compartments/{cell_id}', status_code=204)
    async def retire(id: UUID, cell_id: UUID):
        await invoke(service.retire_compartment(id, cell_id))
        return Response(status_code=204)
    return router
