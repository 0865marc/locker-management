from dataclasses import replace
from uuid import uuid4
from datetime import datetime, timezone
from typing import ClassVar, overload, TypeVar
from collections.abc import Callable
from sqlalchemy.sql.elements import SQLColumnExpression
from domain.lockers import Dimensions
from uuid import UUID

from sqlalchemy import Table, Uuid, CheckConstraint, Column, DateTime, Text, update
from sqlalchemy.ext.asyncio import async_sessionmaker, AsyncSession as SqlAlchemyAsyncSession
from sqlmodel import Field, SQLModel, col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from adapters.database.sqlmodel_lockers import AssignmentRow, CompartmentRow, choose_cell, lock_locker, dimensions
from domain.models import Delivery, DeliveryStatus, Return, ReturnStatus


DELIVERY_STATE = "(status = 'AWAITING_PICKUP' AND collected_at IS NULL AND returned_to_carrier_at IS NULL) OR (status = 'COLLECTED' AND collected_at IS NOT NULL AND returned_to_carrier_at IS NULL) OR (status = 'RETURNED_TO_CARRIER' AND collected_at IS NULL AND returned_to_carrier_at IS NOT NULL)"
RETURN_STATE = "(status = 'AWAITING_CARRIER' AND handed_over_at IS NULL) OR (status = 'HANDED_OVER' AND handed_over_at IS NOT NULL)"


_delivery_table = Table(
    'deliveries', SQLModel.metadata,
    Column('id', Uuid(), primary_key=True, nullable=False),
    Column('tracking_number', Text, nullable=False),
    Column('carrier_code', Text, nullable=False),
    Column('recipient_name', Text, nullable=False),
    Column('recipient_phone', Text),
    Column('received_at', DateTime(timezone=True), nullable=False),
    Column('pickup_deadline_at', DateTime(timezone=True)),
    Column('status', Text, nullable=False),
    Column('collected_at', DateTime(timezone=True)),
    Column('returned_to_carrier_at', DateTime(timezone=True)),
    CheckConstraint(DELIVERY_STATE, name='ck_deliveries_state'),
    CheckConstraint('collected_at IS NULL OR collected_at >= received_at', name='ck_deliveries_collection_time'),
    CheckConstraint('returned_to_carrier_at IS NULL OR returned_to_carrier_at >= received_at', name='ck_deliveries_return_time'),
)


class DeliveryRow(SQLModel, table=True):
    __table__: ClassVar[Table] = _delivery_table

    id: UUID = Field(sa_column=_delivery_table.c.id)
    tracking_number: str = Field(sa_column=_delivery_table.c.tracking_number)
    carrier_code: str = Field(sa_column=_delivery_table.c.carrier_code)
    recipient_name: str = Field(sa_column=_delivery_table.c.recipient_name)
    recipient_phone: str | None = Field(default=None, sa_column=_delivery_table.c.recipient_phone)
    received_at: datetime = Field(sa_column=_delivery_table.c.received_at)
    pickup_deadline_at: datetime | None = Field(default=None, sa_column=_delivery_table.c.pickup_deadline_at)
    status: str = Field(sa_column=_delivery_table.c.status)
    collected_at: datetime | None = Field(default=None, sa_column=_delivery_table.c.collected_at)
    returned_to_carrier_at: datetime | None = Field(default=None, sa_column=_delivery_table.c.returned_to_carrier_at)


_return_table = Table(
    'returns', SQLModel.metadata,
    Column('id', Uuid(), primary_key=True, nullable=False),
    Column('tracking_number', Text, nullable=False),
    Column('carrier_code', Text, nullable=False),
    Column('sender_name', Text),
    Column('received_at', DateTime(timezone=True), nullable=False),
    Column('status', Text, nullable=False),
    Column('handed_over_at', DateTime(timezone=True)),
    CheckConstraint(RETURN_STATE, name='ck_returns_state'),
    CheckConstraint('handed_over_at IS NULL OR handed_over_at >= received_at', name='ck_returns_handover_time'),
)


class ReturnRow(SQLModel, table=True):
    __table__: ClassVar[Table] = _return_table

    id: UUID = Field(sa_column=_return_table.c.id)
    tracking_number: str = Field(sa_column=_return_table.c.tracking_number)
    carrier_code: str = Field(sa_column=_return_table.c.carrier_code)
    sender_name: str | None = Field(default=None, sa_column=_return_table.c.sender_name)
    received_at: datetime = Field(sa_column=_return_table.c.received_at)
    status: str = Field(sa_column=_return_table.c.status)
    handed_over_at: datetime | None = Field(default=None, sa_column=_return_table.c.handed_over_at)


@overload
def _utc(value: datetime) -> datetime: ...


@overload
def _utc(value: None) -> None: ...


def _utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamp must include a timezone")
    return value.astimezone(timezone.utc)


def _delivery(row: DeliveryRow, assignment: AssignmentRow | None = None, cell: CompartmentRow | None = None) -> Delivery:
    return Delivery(
        locker_id=cell.locker_id if assignment is not None and cell is not None else None,
        compartment_id=cell.id if assignment is not None and cell is not None else None,
        parcel_dimensions=dimensions(assignment) if assignment is not None else None,
        id=row.id, tracking_number=row.tracking_number, carrier_code=row.carrier_code,
        recipient_name=row.recipient_name, recipient_phone=row.recipient_phone,
        received_at=_utc(row.received_at), pickup_deadline_at=_utc(row.pickup_deadline_at),
        status=DeliveryStatus(row.status), collected_at=_utc(row.collected_at),
        returned_to_carrier_at=_utc(row.returned_to_carrier_at),
    )


def _return(row: ReturnRow, assignment: AssignmentRow | None = None, cell: CompartmentRow | None = None) -> Return:
    return Return(
        locker_id=cell.locker_id if assignment is not None and cell is not None else None,
        compartment_id=cell.id if assignment is not None and cell is not None else None,
        parcel_dimensions=dimensions(assignment) if assignment is not None else None,
        id=row.id, tracking_number=row.tracking_number, carrier_code=row.carrier_code,
        sender_name=row.sender_name, received_at=_utc(row.received_at),
        status=ReturnStatus(row.status), handed_over_at=_utc(row.handed_over_at),
    )


class SqlModelDeliveryRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def save(self, delivery: Delivery) -> None:
        if delivery.locker_id is not None:
            raise ValueError("Use receive_in_locker for assigned receptions")
        async with self.sessions.begin() as session:
            session.add(DeliveryRow(
                id=delivery.id, tracking_number=delivery.tracking_number,
                carrier_code=delivery.carrier_code, recipient_name=delivery.recipient_name,
                recipient_phone=delivery.recipient_phone, received_at=_utc(delivery.received_at),
                pickup_deadline_at=_utc(delivery.pickup_deadline_at), status=delivery.status.value,
                collected_at=_utc(delivery.collected_at), returned_to_carrier_at=_utc(delivery.returned_to_carrier_at),
            ))

    async def receive_in_locker(self, delivery: Delivery, locker_id: UUID, dimensions: Dimensions) -> Delivery:
        return await _receive(self.sessions, delivery, locker_id, dimensions, DeliveryRow)

    async def list_all(self) -> list[Delivery]:
        return await _read(self.sessions, DeliveryRow, _delivery)

    async def get_by_id(self, identifier: UUID) -> Delivery | None:
        rows = await _read(self.sessions, DeliveryRow, _delivery, identifier)
        return rows[0] if rows else None

    async def save_exit(self, delivery: Delivery) -> bool:
        if delivery.status is DeliveryStatus.AWAITING_PICKUP:
            raise ValueError("A custody exit requires a terminal delivery")
        async with self.sessions.begin() as session:
            assignment = await _lock_assignment(session, DeliveryRow, delivery.id)
            result = await SqlAlchemyAsyncSession.execute(session,
                update(DeliveryRow).where(
                    col(DeliveryRow.id) == delivery.id,
                    col(DeliveryRow.status) == DeliveryStatus.AWAITING_PICKUP.value,
                ).values(status=delivery.status.value, collected_at=_utc(delivery.collected_at),
                         returned_to_carrier_at=_utc(delivery.returned_to_carrier_at)).returning(col(DeliveryRow.id))
            )
            changed = result.scalar_one_or_none() is not None
            if changed:
                await _release(session, assignment, delivery.collected_at or delivery.returned_to_carrier_at)
        return changed


class SqlModelReturnRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def save(self, item: Return) -> None:
        if item.locker_id is not None:
            raise ValueError("Use receive_in_locker for assigned receptions")
        async with self.sessions.begin() as session:
            session.add(ReturnRow(
                id=item.id, tracking_number=item.tracking_number, carrier_code=item.carrier_code,
                sender_name=item.sender_name, received_at=_utc(item.received_at),
                status=item.status.value, handed_over_at=_utc(item.handed_over_at),
            ))

    async def receive_in_locker(self, item: Return, locker_id: UUID, dimensions: Dimensions) -> Return:
        return await _receive(self.sessions, item, locker_id, dimensions, ReturnRow)

    async def list_all(self) -> list[Return]:
        return await _read(self.sessions, ReturnRow, _return)

    async def get_by_id(self, identifier: UUID) -> Return | None:
        rows = await _read(self.sessions, ReturnRow, _return, identifier)
        return rows[0] if rows else None

    async def save_exit(self, item: Return) -> bool:
        if item.status is ReturnStatus.AWAITING_CARRIER:
            raise ValueError("A custody exit requires a terminal return")
        async with self.sessions.begin() as session:
            assignment = await _lock_assignment(session, ReturnRow, item.id)
            result = await SqlAlchemyAsyncSession.execute(session,
                update(ReturnRow).where(
                    col(ReturnRow.id) == item.id,
                    col(ReturnRow.status) == ReturnStatus.AWAITING_CARRIER.value,
                ).values(status=item.status.value, handed_over_at=_utc(item.handed_over_at)).returning(col(ReturnRow.id))
            )
            changed = result.scalar_one_or_none() is not None
            if changed:
                await _release(session, assignment, item.handed_over_at)
        return changed


RowT = TypeVar('RowT', DeliveryRow, ReturnRow)
EntityT = TypeVar('EntityT', Delivery, Return)


def _parcel_fk(row_type: type[DeliveryRow] | type[ReturnRow]) -> SQLColumnExpression[UUID | None]:
    return col(AssignmentRow.delivery_id) if row_type is DeliveryRow else col(AssignmentRow.return_id)


async def _read(sessions: async_sessionmaker[AsyncSession], row_type: type[RowT],
                convert: Callable[[RowT, AssignmentRow | None, CompartmentRow | None], EntityT],
                identifier: UUID | None = None) -> list[EntityT]:
    async with sessions() as session:
        query = select(row_type, AssignmentRow, CompartmentRow).outerjoin(AssignmentRow, _parcel_fk(row_type) == col(row_type.id)).outerjoin(CompartmentRow, col(CompartmentRow.id) == col(AssignmentRow.compartment_id))
        if identifier is not None:
            query = query.where(col(row_type.id) == identifier)
        rows = await session.exec(query.order_by(col(row_type.id)))
        return [convert(row, assignment, cell) for row, assignment, cell in rows]


async def _receive(sessions: async_sessionmaker[AsyncSession], entity: EntityT, locker_id: UUID,
                   parcel_dimensions: Dimensions, row_type: type[DeliveryRow] | type[ReturnRow]) -> EntityT:
    if entity.locker_id is not None:
        raise ValueError('Reception requires an unassigned entity')
    pending = DeliveryStatus.AWAITING_PICKUP if row_type is DeliveryRow else ReturnStatus.AWAITING_CARRIER
    if entity.status != pending:
        raise ValueError('Reception requires pending custody')
    async with sessions.begin() as session:
        cell = await choose_cell(session, locker_id, parcel_dimensions)
        if isinstance(entity, Delivery):
            session.add(DeliveryRow(id=entity.id, tracking_number=entity.tracking_number,
                carrier_code=entity.carrier_code, recipient_name=entity.recipient_name,
                recipient_phone=entity.recipient_phone, received_at=entity.received_at,
                pickup_deadline_at=entity.pickup_deadline_at, status=entity.status.value,
                collected_at=entity.collected_at, returned_to_carrier_at=entity.returned_to_carrier_at))
        else:
            session.add(ReturnRow(id=entity.id, tracking_number=entity.tracking_number,
                carrier_code=entity.carrier_code, sender_name=entity.sender_name,
                received_at=entity.received_at, status=entity.status.value, handed_over_at=entity.handed_over_at))
        await session.flush()
        session.add(AssignmentRow(id=uuid4(), compartment_id=cell.id,
            delivery_id=entity.id if row_type is DeliveryRow else None,
            return_id=entity.id if row_type is ReturnRow else None,
            width_mm=parcel_dimensions.width_mm, height_mm=parcel_dimensions.height_mm,
            depth_mm=parcel_dimensions.depth_mm, assigned_at=_utc(entity.received_at)))
        await session.flush()
        result = replace(entity, locker_id=locker_id, compartment_id=cell.id, parcel_dimensions=parcel_dimensions)
    return result


async def _lock_assignment(session: AsyncSession, row_type: type[DeliveryRow] | type[ReturnRow], identifier: UUID) -> AssignmentRow | None:
    # Lookup is nonlocking and immutable. Acquire locker lock before any parcel/assignment update.
    result = await session.exec(select(AssignmentRow, col(CompartmentRow.locker_id)).join(CompartmentRow, col(CompartmentRow.id) == col(AssignmentRow.compartment_id)).where(_parcel_fk(row_type) == identifier))
    found = result.one_or_none()
    if found is None:
        return None
    assignment, locker_id = found
    await lock_locker(session, locker_id)
    # READ COMMITTED: refresh after a possible wait for the locker lock.
    await session.refresh(assignment)
    return assignment


async def _release(session: AsyncSession, assignment: AssignmentRow | None, at: datetime | None) -> None:
    if assignment is None:
        return
    if assignment.released_at is not None:
        raise RuntimeError('Pending assigned parcel has no active assignment')
    if at is None:
        raise ValueError('A custody exit requires a timestamp')
    result = await SqlAlchemyAsyncSession.execute(session, update(AssignmentRow).where(col(AssignmentRow.id) == assignment.id, col(AssignmentRow.released_at) == None).values(released_at=_utc(at)).returning(col(AssignmentRow.id)))
    if result.scalar_one_or_none() is None:
        raise RuntimeError('Pending assigned parcel has no active assignment')
