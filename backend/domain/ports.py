from typing import Protocol

from domain.models import Delivery, Return


class DeliveryRepository(Protocol):
    """Puerto de salida para guardar y consultar entregas."""

    async def save(self, delivery: Delivery) -> None: ...

    async def list_all(self) -> list[Delivery]: ...


class ReturnRepository(Protocol):
    """Puerto de salida para guardar y consultar devoluciones."""

    async def save(self, item: Return) -> None: ...

    async def list_all(self) -> list[Return]: ...
