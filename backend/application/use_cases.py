from collections.abc import Callable
from datetime import datetime, timezone
from uuid import UUID

from domain.lockers import Dimensions, require_instance
from domain.models import CustodyConflictError, Delivery, Return
from domain.ports import DeliveryRepository, ReturnRepository


class ParcelNotFoundError(LookupError):
    """No parcel exists with the requested UUID in this flow."""


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DeliveryService:
    def __init__(self, repository: DeliveryRepository, clock: Callable[[], datetime] = utc_now) -> None:
        self.repository = repository
        self.clock = clock

    async def create(
        self,
        tracking_number: str,
        carrier_code: str,
        recipient_name: str,
        recipient_phone: str | None = None,
        pickup_deadline_at: datetime | None = None,
        locker_id: UUID | None = None,
        parcel_dimensions: Dimensions | None = None,
    ) -> Delivery:
        delivery = Delivery(
            tracking_number=tracking_number,
            carrier_code=carrier_code,
            recipient_name=recipient_name,
            recipient_phone=recipient_phone,
            pickup_deadline_at=pickup_deadline_at,
            received_at=self.clock(),
        )
        _validate_reception(locker_id, parcel_dimensions)
        if locker_id is not None and parcel_dimensions is not None:
            return await self.repository.receive_in_locker(delivery, locker_id, parcel_dimensions)
        await self.repository.save(delivery)
        return delivery

    async def list_all(self) -> list[Delivery]:
        return await self.repository.list_all()

    async def collect(self, identifier: UUID) -> Delivery:
        delivery = await self._find(identifier)
        return await self._save_parcel_departure(delivery.collect(self.clock()))

    async def return_to_carrier(self, identifier: UUID) -> Delivery:
        delivery = await self._find(identifier)
        return await self._save_parcel_departure(delivery.return_to_carrier(self.clock()))

    async def _find(self, identifier: UUID) -> Delivery:
        delivery = await self.repository.get_by_id(identifier)
        if delivery is None:
            raise ParcelNotFoundError("Delivery no encontrada")
        return delivery

    async def _save_parcel_departure(self, delivery: Delivery) -> Delivery:
        if not await self.repository.save_exit(delivery):
            raise CustodyConflictError("Otro proceso ya ha registrado la salida del paquete")
        return delivery


class ReturnService:
    def __init__(self, repository: ReturnRepository, clock: Callable[[], datetime] = utc_now) -> None:
        self.repository = repository
        self.clock = clock

    async def create(self, tracking_number: str, carrier_code: str, sender_name: str | None = None, locker_id: UUID | None = None, parcel_dimensions: Dimensions | None = None) -> Return:
        item = Return(
            tracking_number=tracking_number,
            carrier_code=carrier_code,
            sender_name=sender_name,
            received_at=self.clock(),
        )
        _validate_reception(locker_id, parcel_dimensions)
        if locker_id is not None and parcel_dimensions is not None:
            return await self.repository.receive_in_locker(item, locker_id, parcel_dimensions)
        await self.repository.save(item)
        return item

    async def list_all(self) -> list[Return]:
        return await self.repository.list_all()

    async def hand_over(self, identifier: UUID) -> Return:
        item = await self.repository.get_by_id(identifier)
        if item is None:
            raise ParcelNotFoundError("Return no encontrada")
        updated = item.hand_over(self.clock())
        if not await self.repository.save_exit(updated):
            raise CustodyConflictError("Otro proceso ya ha registrado la salida del paquete")
        return updated


def _validate_reception(locker_id: UUID | None, dimensions: Dimensions | None) -> None:
    if (locker_id is None) != (dimensions is None):
        raise ValueError("locker_id y parcel_dimensions deben indicarse juntos")
    if locker_id is not None:
        require_instance(locker_id, UUID, "Asignación inválida")
        require_instance(dimensions, Dimensions, "Asignación inválida")
