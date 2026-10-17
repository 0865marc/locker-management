from typing import Protocol
from uuid import UUID

from domain.deliveries import Delivery
from domain.lockers import Dimensions


class DeliveryRepository(Protocol):
    """Puerto de salida para guardar y consultar entregas."""

    async def save(self, delivery: Delivery) -> None: ...

    async def receive_in_locker(
        self, delivery: Delivery, locker_id: UUID, dimensions: Dimensions
    ) -> Delivery: ...

    async def list_all(self) -> list[Delivery]: ...

    async def get_by_id(self, identifier: UUID) -> Delivery | None: ...

    async def save_exit(self, delivery: Delivery) -> bool:
        """Persist a terminal state only while stored custody is pending."""
        ...
