from collections.abc import Callable
from datetime import datetime
from uuid import UUID

from application.deliveries.ports import DeliveryRepository
from domain.deliveries import Delivery, DeliveryConflictError
from domain.lockers import Dimensions, validate_reception


class DeliveryNotFoundError(LookupError):
    """No parcel exists with the requested UUID in this flow."""


class DeliveryService:
    def __init__(
        self, repository: DeliveryRepository, clock: Callable[[], datetime]
    ) -> None:
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
        validate_reception(locker_id, parcel_dimensions)
        if locker_id is not None and parcel_dimensions is not None:
            return await self.repository.receive_in_locker(
                delivery, locker_id, parcel_dimensions
            )
        await self.repository.save(delivery)
        return delivery

    async def list_all(self) -> list[Delivery]:
        return await self.repository.list_all()

    async def collect(self, identifier: UUID) -> Delivery:
        delivery = await self._find(identifier)
        return await self._save_parcel_departure(delivery.collect(self.clock()))

    async def return_to_carrier(self, identifier: UUID) -> Delivery:
        delivery = await self._find(identifier)
        return await self._save_parcel_departure(
            delivery.return_to_carrier(self.clock())
        )

    async def _find(self, identifier: UUID) -> Delivery:
        delivery = await self.repository.get_by_id(identifier)
        if delivery is None:
            raise DeliveryNotFoundError("Delivery no encontrada")
        return delivery

    async def _save_parcel_departure(self, delivery: Delivery) -> Delivery:
        if not await self.repository.save_exit(delivery):
            raise DeliveryConflictError(
                "Otro proceso ya ha registrado la salida del paquete"
            )
        return delivery
