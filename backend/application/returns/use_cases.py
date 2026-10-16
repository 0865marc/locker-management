from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from application.returns.ports import ReturnRepository
from domain.lockers import Dimensions, validate_reception
from domain.returns import Return, ReturnConflictError


class ReturnNotFoundError(LookupError):
    """No parcel exists with the requested UUID in this flow."""


class ReturnService:
    def __init__(
        self, repository: ReturnRepository, clock: Callable[[], datetime]
    ) -> None:
        self.repository = repository
        self.clock = clock

    async def create(
        self,
        tracking_number: str,
        carrier_code: str,
        sender_name: str | None = None,
        locker_id: UUID | None = None,
        parcel_dimensions: Dimensions | None = None,
    ) -> Return:
        item = Return(
            tracking_number=tracking_number,
            carrier_code=carrier_code,
            sender_name=sender_name,
            received_at=self.clock(),
        )
        validate_reception(locker_id, parcel_dimensions)
        if locker_id is not None and parcel_dimensions is not None:
            return await self.repository.receive_in_locker(
                item, locker_id, parcel_dimensions
            )
        await self.repository.save(item)
        return item

    async def list_all(self) -> list[Return]:
        return await self.repository.list_all()

    async def hand_over(self, identifier: UUID) -> Return:
        item = await self.repository.get_by_id(identifier)
        if item is None:
            raise ReturnNotFoundError("Return no encontrada")
        updated = item.hand_over(self.clock())
        if not await self.repository.save_exit(updated):
            raise ReturnConflictError(
                "Otro proceso ya ha registrado la salida del paquete"
            )
        return updated
