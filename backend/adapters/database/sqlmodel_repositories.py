from datetime import datetime, timezone
from typing import overload
from uuid import UUID

from sqlalchemy import CheckConstraint, Column, DateTime, Text, update
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import Field, SQLModel, col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from domain.models import Delivery, DeliveryStatus, Return, ReturnStatus


DELIVERY_STATE = "(status = 'AWAITING_PICKUP' AND collected_at IS NULL AND returned_to_carrier_at IS NULL) OR (status = 'COLLECTED' AND collected_at IS NOT NULL AND returned_to_carrier_at IS NULL) OR (status = 'RETURNED_TO_CARRIER' AND collected_at IS NULL AND returned_to_carrier_at IS NOT NULL)"
RETURN_STATE = "(status = 'AWAITING_CARRIER' AND handed_over_at IS NULL) OR (status = 'HANDED_OVER' AND handed_over_at IS NOT NULL)"


class DeliveryRow(SQLModel, table=True):
    # SQLModel types this string override as a declared_attr descriptor.
    __tablename__ = "deliveries"  # pyright: ignore[reportAssignmentType]

    __table_args__ = (
        CheckConstraint(DELIVERY_STATE, name="ck_deliveries_state"),
        CheckConstraint("collected_at IS NULL OR collected_at >= received_at", name="ck_deliveries_collection_time"),
        CheckConstraint("returned_to_carrier_at IS NULL OR returned_to_carrier_at >= received_at", name="ck_deliveries_return_time"),
    )

    id: UUID = Field(primary_key=True)
    tracking_number: str = Field(sa_column=Column(Text, nullable=False))
    carrier_code: str = Field(sa_column=Column(Text, nullable=False))
    recipient_name: str = Field(sa_column=Column(Text, nullable=False))
    recipient_phone: str | None = Field(default=None, sa_column=Column(Text))
    received_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    pickup_deadline_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    status: str = Field(sa_column=Column(Text, nullable=False))
    collected_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))
    returned_to_carrier_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))


class ReturnRow(SQLModel, table=True):
    # SQLModel types this string override as a declared_attr descriptor.
    __tablename__ = "returns"  # pyright: ignore[reportAssignmentType]

    __table_args__ = (
        CheckConstraint(RETURN_STATE, name="ck_returns_state"),
        CheckConstraint("handed_over_at IS NULL OR handed_over_at >= received_at", name="ck_returns_handover_time"),
    )

    id: UUID = Field(primary_key=True)
    tracking_number: str = Field(sa_column=Column(Text, nullable=False))
    carrier_code: str = Field(sa_column=Column(Text, nullable=False))
    sender_name: str | None = Field(default=None, sa_column=Column(Text))
    received_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    status: str = Field(sa_column=Column(Text, nullable=False))
    handed_over_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))


@overload
def _utc(value: datetime) -> datetime: ...


@overload
def _utc(value: None) -> None: ...


def _utc(value: datetime | None) -> datetime | None:
    # SQLite returns naive timestamps for values stored in UTC.
    if value is None:
        return None
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _delivery(row: DeliveryRow) -> Delivery:
    return Delivery(
        id=row.id, tracking_number=row.tracking_number, carrier_code=row.carrier_code,
        recipient_name=row.recipient_name, recipient_phone=row.recipient_phone,
        received_at=_utc(row.received_at), pickup_deadline_at=_utc(row.pickup_deadline_at),
        status=DeliveryStatus(row.status), collected_at=_utc(row.collected_at),
        returned_to_carrier_at=_utc(row.returned_to_carrier_at),
    )


def _return(row: ReturnRow) -> Return:
    return Return(
        id=row.id, tracking_number=row.tracking_number, carrier_code=row.carrier_code,
        sender_name=row.sender_name, received_at=_utc(row.received_at),
        status=ReturnStatus(row.status), handed_over_at=_utc(row.handed_over_at),
    )


class SqlModelDeliveryRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def save(self, delivery: Delivery) -> None:
        async with self.sessions.begin() as session:
            session.add(DeliveryRow(
                id=delivery.id, tracking_number=delivery.tracking_number,
                carrier_code=delivery.carrier_code, recipient_name=delivery.recipient_name,
                recipient_phone=delivery.recipient_phone, received_at=_utc(delivery.received_at),
                pickup_deadline_at=_utc(delivery.pickup_deadline_at), status=delivery.status.value,
                collected_at=_utc(delivery.collected_at), returned_to_carrier_at=_utc(delivery.returned_to_carrier_at),
            ))

    async def list_all(self) -> list[Delivery]:
        async with self.sessions() as session:
            rows = await session.exec(select(DeliveryRow).order_by(col(DeliveryRow.id)))
            return [_delivery(row) for row in rows]

    async def get_by_id(self, identifier: UUID) -> Delivery | None:
        async with self.sessions() as session:
            row = await session.get(DeliveryRow, identifier)
            return _delivery(row) if row is not None else None

    async def save_exit(self, delivery: Delivery) -> bool:
        if delivery.status is DeliveryStatus.AWAITING_PICKUP:
            raise ValueError("A custody exit requires a terminal delivery")
        async with self.sessions.begin() as session:
            result = await session.exec(
                update(DeliveryRow).where(
                    col(DeliveryRow.id) == delivery.id,
                    col(DeliveryRow.status) == DeliveryStatus.AWAITING_PICKUP.value,
                ).values(status=delivery.status.value, collected_at=_utc(delivery.collected_at),
                         returned_to_carrier_at=_utc(delivery.returned_to_carrier_at))
            )
            changed = result.rowcount == 1
        return changed


class SqlModelReturnRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def save(self, item: Return) -> None:
        async with self.sessions.begin() as session:
            session.add(ReturnRow(
                id=item.id, tracking_number=item.tracking_number, carrier_code=item.carrier_code,
                sender_name=item.sender_name, received_at=_utc(item.received_at),
                status=item.status.value, handed_over_at=_utc(item.handed_over_at),
            ))

    async def list_all(self) -> list[Return]:
        async with self.sessions() as session:
            rows = await session.exec(select(ReturnRow).order_by(col(ReturnRow.id)))
            return [_return(row) for row in rows]

    async def get_by_id(self, identifier: UUID) -> Return | None:
        async with self.sessions() as session:
            row = await session.get(ReturnRow, identifier)
            return _return(row) if row is not None else None

    async def save_exit(self, item: Return) -> bool:
        if item.status is ReturnStatus.AWAITING_CARRIER:
            raise ValueError("A custody exit requires a terminal return")
        async with self.sessions.begin() as session:
            result = await session.exec(
                update(ReturnRow).where(
                    col(ReturnRow.id) == item.id,
                    col(ReturnRow.status) == ReturnStatus.AWAITING_CARRIER.value,
                ).values(status=item.status.value, handed_over_at=_utc(item.handed_over_at))
            )
            changed = result.rowcount == 1
        return changed
