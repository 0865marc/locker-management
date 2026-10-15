from uuid import UUID
from domain.lockers import CompartmentBatch, Dimensions, Locker, LockerNotFoundError, validate_batches
from domain.ports import LockerRepository


def location(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('location_id debe ser texto no vacío')
    return value.strip()


class LockerService:
    def __init__(self, repository: LockerRepository):
        self.repository = repository

    async def create(self, location_id, batches, active=True):
        validate_batches(batches)
        Locker(location_id=location_id, active=active)
        return await self.repository.create(location(location_id), batches, active)

    async def list_all(self, location_id=None):
        return await self.repository.list_all(location(location_id) if location_id is not None else None)

    async def get_by_id(self, identifier):
        item = await self.repository.get_by_id(identifier)
        if item is None:
            raise LockerNotFoundError('Locker no encontrado')
        return item

    async def set_active(self, identifier, active):
        if type(active) is not bool:
            raise ValueError('active debe ser booleano')
        return await self.repository.set_active(identifier, active)

    async def add_compartments(self, identifier, batches):
        validate_batches(batches)
        return await self.repository.add_compartments(identifier, batches)

    async def update_compartment(self, identifier, cell_id, dimensions=None, enabled=None):
        if dimensions is None and enabled is None:
            raise ValueError('Se requiere dimensions o enabled')
        if dimensions is not None and not isinstance(dimensions, Dimensions):
            raise ValueError('Dimensiones inválidas')
        if enabled is not None and type(enabled) is not bool:
            raise ValueError('enabled debe ser booleano')
        return await self.repository.update_compartment(identifier, cell_id, dimensions, enabled)

    async def retire_compartment(self, identifier, cell_id):
        await self.repository.retire_compartment(identifier, cell_id)

    async def availability(self, location_id, dimensions):
        return await self.repository.availability(location(location_id), dimensions)
