from typing import Protocol
from uuid import UUID

from domain.returns import Return
from domain.lockers import Dimensions


class ReturnRepository(Protocol):
    """Puerto de salida para guardar y consultar devoluciones."""

    async def save(self, item: Return) -> None: ...

    async def receive_in_locker(self, item: Return, locker_id: UUID, dimensions: Dimensions) -> Return: ...

    async def list_all(self) -> list[Return]: ...

    async def get_by_id(self, identifier: UUID) -> Return | None: ...

    async def save_exit(self, item: Return) -> bool:
        """Persist a terminal state only while stored custody is pending."""
        ...
