from domain.models import Delivery, Return
from domain.ports import DeliveryRepository, ReturnRepository


class DeliveryService:
    def __init__(self, repository: DeliveryRepository) -> None:
        self.repository = repository

    async def create(self, address: str) -> Delivery:
        delivery = Delivery(address=address)
        await self.repository.save(delivery)
        return delivery

    async def list_all(self) -> list[Delivery]:
        return await self.repository.list_all()


class ReturnService:
    def __init__(self, repository: ReturnRepository) -> None:
        self.repository = repository

    async def create(self, reason: str) -> Return:
        item = Return(reason=reason)
        await self.repository.save(item)
        return item

    async def list_all(self) -> list[Return]:
        return await self.repository.list_all()
