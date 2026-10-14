from uuid import UUID

from sqlalchemy import Column, Text
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import Field, SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession

from domain.models import Delivery, Return


class DeliveryRow(SQLModel, table=True):
    __tablename__ = "deliveries"

    id: UUID = Field(primary_key=True)
    address: str = Field(sa_column=Column(Text, nullable=False))


class ReturnRow(SQLModel, table=True):
    __tablename__ = "returns"

    id: UUID = Field(primary_key=True)
    reason: str = Field(sa_column=Column(Text, nullable=False))


class SqlModelDeliveryRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def save(self, delivery: Delivery) -> None:
        # Una transacción por escritura: commit al salir, rollback si falla.
        async with self.sessions.begin() as session:
            session.add(DeliveryRow(id=delivery.id, address=delivery.address))

    async def list_all(self) -> list[Delivery]:
        async with self.sessions() as session:
            rows = await session.exec(select(DeliveryRow).order_by(DeliveryRow.id))
            return [Delivery(id=row.id, address=row.address) for row in rows]


class SqlModelReturnRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def save(self, item: Return) -> None:
        async with self.sessions.begin() as session:
            session.add(ReturnRow(id=item.id, reason=item.reason))

    async def list_all(self) -> list[Return]:
        async with self.sessions() as session:
            rows = await session.exec(select(ReturnRow).order_by(ReturnRow.id))
            return [Return(id=row.id, reason=row.reason) for row in rows]
