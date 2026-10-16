from dataclasses import replace
from datetime import datetime
from typing import ClassVar
from uuid import UUID

from sqlalchemy import CheckConstraint, Column, DateTime, Table, Text, Uuid, update
from sqlalchemy.ext.asyncio import AsyncSession as SqlAlchemyAsyncSession
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import Field, SQLModel, col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from adapters.database.sqlmodel_lockers import (
    AssignmentRow,
    CompartmentRow,
    choose_cell,
    dimensions,
    lock_assignment,
    record_assignment,
    release_assignment,
    utc_timestamp,
)
from domain.deliveries import Delivery, DeliveryStatus
from domain.lockers import Dimensions

DELIVERY_STATE = "(status = 'AWAITING_PICKUP' AND collected_at IS NULL AND returned_to_carrier_at IS NULL) OR (status = 'COLLECTED' AND collected_at IS NOT NULL AND returned_to_carrier_at IS NULL) OR (status = 'RETURNED_TO_CARRIER' AND collected_at IS NULL AND returned_to_carrier_at IS NOT NULL)"


_delivery_table = Table(
    "deliveries",
    SQLModel.metadata,
    Column("id", Uuid(), primary_key=True, nullable=False),
    Column("tracking_number", Text, nullable=False),
    Column("carrier_code", Text, nullable=False),
    Column("recipient_name", Text, nullable=False),
    Column("recipient_phone", Text),
    Column("received_at", DateTime(timezone=True), nullable=False),
    Column("pickup_deadline_at", DateTime(timezone=True)),
    Column("status", Text, nullable=False),
    Column("collected_at", DateTime(timezone=True)),
    Column("returned_to_carrier_at", DateTime(timezone=True)),
    CheckConstraint(DELIVERY_STATE, name="ck_deliveries_state"),
    CheckConstraint(
        "collected_at IS NULL OR collected_at >= received_at",
        name="ck_deliveries_collection_time",
    ),
    CheckConstraint(
        "returned_to_carrier_at IS NULL OR returned_to_carrier_at >= received_at",
        name="ck_deliveries_return_time",
    ),
)


class DeliveryRow(SQLModel, table=True):
    __table__: ClassVar[Table] = _delivery_table

    id: UUID = Field(sa_column=_delivery_table.c.id)
    tracking_number: str = Field(sa_column=_delivery_table.c.tracking_number)
    carrier_code: str = Field(sa_column=_delivery_table.c.carrier_code)
    recipient_name: str = Field(sa_column=_delivery_table.c.recipient_name)
    recipient_phone: str | None = Field(
        default=None, sa_column=_delivery_table.c.recipient_phone
    )
    received_at: datetime = Field(sa_column=_delivery_table.c.received_at)
    pickup_deadline_at: datetime | None = Field(
        default=None, sa_column=_delivery_table.c.pickup_deadline_at
    )
    status: str = Field(sa_column=_delivery_table.c.status)
    collected_at: datetime | None = Field(
        default=None, sa_column=_delivery_table.c.collected_at
    )
    returned_to_carrier_at: datetime | None = Field(
        default=None, sa_column=_delivery_table.c.returned_to_carrier_at
    )


def _delivery(
    row: DeliveryRow,
    assignment: AssignmentRow | None = None,
    cell: CompartmentRow | None = None,
) -> Delivery:
    return Delivery(
        locker_id=cell.locker_id
        if assignment is not None and cell is not None
        else None,
        compartment_id=cell.id if assignment is not None and cell is not None else None,
        parcel_dimensions=dimensions(assignment) if assignment is not None else None,
        id=row.id,
        tracking_number=row.tracking_number,
        carrier_code=row.carrier_code,
        recipient_name=row.recipient_name,
        recipient_phone=row.recipient_phone,
        received_at=utc_timestamp(row.received_at),
        pickup_deadline_at=utc_timestamp(row.pickup_deadline_at),
        status=DeliveryStatus(row.status),
        collected_at=utc_timestamp(row.collected_at),
        returned_to_carrier_at=utc_timestamp(row.returned_to_carrier_at),
    )


def _row(delivery: Delivery) -> DeliveryRow:
    return DeliveryRow(
        id=delivery.id,
        tracking_number=delivery.tracking_number,
        carrier_code=delivery.carrier_code,
        recipient_name=delivery.recipient_name,
        recipient_phone=delivery.recipient_phone,
        received_at=utc_timestamp(delivery.received_at),
        pickup_deadline_at=utc_timestamp(delivery.pickup_deadline_at),
        status=delivery.status.value,
        collected_at=utc_timestamp(delivery.collected_at),
        returned_to_carrier_at=utc_timestamp(delivery.returned_to_carrier_at),
    )


class SqlModelDeliveryRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def save(self, delivery: Delivery) -> None:
        if delivery.locker_id is not None:
            raise ValueError("Use receive_in_locker for assigned receptions")
        async with self.sessions.begin() as session:
            session.add(_row(delivery))

    async def receive_in_locker(
        self, delivery: Delivery, locker_id: UUID, dimensions: Dimensions
    ) -> Delivery:
        if delivery.locker_id is not None:
            raise ValueError("Reception requires an unassigned entity")
        if delivery.status != DeliveryStatus.AWAITING_PICKUP:
            raise ValueError("Reception requires pending custody")
        async with self.sessions.begin() as session:
            cell = await choose_cell(session, locker_id, dimensions)
            session.add(_row(delivery))
            await session.flush()
            await record_assignment(
                session,
                cell.id,
                dimensions,
                delivery.received_at,
                delivery_id=delivery.id,
            )
            result = replace(
                delivery,
                locker_id=locker_id,
                compartment_id=cell.id,
                parcel_dimensions=dimensions,
            )
        return result

    async def list_all(self) -> list[Delivery]:
        return await self._read()

    async def get_by_id(self, identifier: UUID) -> Delivery | None:
        rows = await self._read(identifier)
        return rows[0] if rows else None

    async def _read(self, identifier: UUID | None = None) -> list[Delivery]:
        async with self.sessions() as session:
            query = (
                select(DeliveryRow, AssignmentRow, CompartmentRow)
                .outerjoin(
                    AssignmentRow, col(AssignmentRow.delivery_id) == col(DeliveryRow.id)
                )
                .outerjoin(
                    CompartmentRow,
                    col(CompartmentRow.id) == col(AssignmentRow.compartment_id),
                )
            )
            if identifier is not None:
                query = query.where(col(DeliveryRow.id) == identifier)
            rows = await session.exec(query.order_by(col(DeliveryRow.id)))
            return [_delivery(row, assignment, cell) for row, assignment, cell in rows]

    async def save_exit(self, delivery: Delivery) -> bool:
        if delivery.status is DeliveryStatus.AWAITING_PICKUP:
            raise ValueError("A custody exit requires a terminal delivery")
        async with self.sessions.begin() as session:
            assignment = await lock_assignment(
                session, col(AssignmentRow.delivery_id), delivery.id
            )
            result = await SqlAlchemyAsyncSession.execute(
                session,
                update(DeliveryRow)
                .where(
                    col(DeliveryRow.id) == delivery.id,
                    col(DeliveryRow.status) == DeliveryStatus.AWAITING_PICKUP.value,
                )
                .values(
                    status=delivery.status.value,
                    collected_at=utc_timestamp(delivery.collected_at),
                    returned_to_carrier_at=utc_timestamp(
                        delivery.returned_to_carrier_at
                    ),
                )
                .returning(col(DeliveryRow.id)),
            )
            changed = result.scalar_one_or_none() is not None
            if changed:
                await release_assignment(
                    session,
                    assignment,
                    delivery.collected_at or delivery.returned_to_carrier_at,
                )
        return changed
