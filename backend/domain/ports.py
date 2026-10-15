from typing import Protocol
from uuid import UUID

from domain.models import Delivery, Return


class DeliveryRepository(Protocol):
    """Puerto de salida para guardar y consultar entregas."""

    async def save(self, delivery: Delivery) -> None: ...

    async def list_all(self) -> list[Delivery]: ...

    async def get_by_id(self, identifier: UUID) -> Delivery | None: ...

    async def save_exit(self, delivery: Delivery) -> bool:
        """Persist a terminal state only while stored custody is pending."""
        ...


class ReturnRepository(Protocol):
    """Puerto de salida para guardar y consultar devoluciones."""

    async def save(self, item: Return) -> None: ...

    async def list_all(self) -> list[Return]: ...

    async def get_by_id(self, identifier: UUID) -> Return | None: ...

    async def save_exit(self, item: Return) -> bool:
        """Persist a terminal state only while stored custody is pending."""
        ...
