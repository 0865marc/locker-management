from uuid import UUID
from domain.lockers import (Address, Availability, Compartment, CompartmentBatch, Coordinates,
    Dimensions, Locker, LockerNotFoundError, LockerPatch, location_alias, validate_batches, require_instance)
from application.lockers.ports import LockerRepository


class LockerService:
    def __init__(self, repository: LockerRepository) -> None:
        self.repository = repository

    async def create(self, location_id: str | None, batches: list[CompartmentBatch], active: bool = True,
                     address: Address | None = None, coordinates: Coordinates | None = None) -> Locker:
        validate_batches(batches)
        locker = Locker(location_id=location_id, active=active, address=address, coordinates=coordinates)
        if locker.location_id is None and locker.address is None:
            raise ValueError('Se requiere location_id o address para crear un locker')
        # Preserve the established positional contract for legacy callers.
        if address is None and coordinates is None:
            return await self.repository.create(locker.location_id, batches, active)
        return await self.repository.create(locker.location_id, batches, active, address, coordinates)

    async def list_all(self, location_id: str | None = None) -> list[Locker]:
        return await self.repository.list_all(location_alias(location_id) if location_id is not None else None)

    async def get_by_id(self, identifier: UUID) -> Locker:
        item = await self.repository.get_by_id(identifier)
        if item is None:
            raise LockerNotFoundError('Locker no encontrado')
        return item

    async def set_active(self, identifier: UUID, active: bool) -> Locker:
        if type(active) is not bool:
            raise ValueError('active debe ser booleano')
        return await self.repository.set_active(identifier, active)

    async def update(self, identifier: UUID, patch: LockerPatch) -> Locker:
        return await self.repository.update(identifier, patch)

    async def add_compartments(self, identifier: UUID, batches: list[CompartmentBatch]) -> Locker:
        validate_batches(batches)
        return await self.repository.add_compartments(identifier, batches)

    async def update_compartment(self, identifier: UUID, cell_id: UUID, dimensions: Dimensions | None = None, enabled: bool | None = None) -> Compartment:
        if dimensions is None and enabled is None:
            raise ValueError('Se requiere dimensions o enabled')
        if dimensions is not None:
            require_instance(dimensions, Dimensions, 'Dimensiones inválidas')
        if enabled is not None and type(enabled) is not bool:
            raise ValueError('enabled debe ser booleano')
        return await self.repository.update_compartment(identifier, cell_id, dimensions, enabled)

    async def retire_compartment(self, identifier: UUID, cell_id: UUID) -> None:
        await self.repository.retire_compartment(identifier, cell_id)

    async def availability(self, location_id: str, dimensions: Dimensions) -> Availability:
        return await self.repository.availability(location_alias(location_id), dimensions)
