from dataclasses import replace
from uuid import uuid4
from datetime import datetime, timezone
from typing import overload
from uuid import UUID

from sqlalchemy import CheckConstraint, Column, DateTime, Text, update
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import Field, SQLModel, col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from adapters.database.sqlmodel_lockers import AssignmentRow, CompartmentRow, choose_cell, lock_locker, dimensions
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


def _delivery(row: DeliveryRow, assignment=None, cell=None) -> Delivery:
    return Delivery(
        **_assignment_fields(assignment, cell),
        id=row.id, tracking_number=row.tracking_number, carrier_code=row.carrier_code,
        recipient_name=row.recipient_name, recipient_phone=row.recipient_phone,
        received_at=_utc(row.received_at), pickup_deadline_at=_utc(row.pickup_deadline_at),
        status=DeliveryStatus(row.status), collected_at=_utc(row.collected_at),
        returned_to_carrier_at=_utc(row.returned_to_carrier_at),
    )


def _return(row: ReturnRow, assignment=None, cell=None) -> Return:
    return Return(
        **_assignment_fields(assignment, cell),
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

    async def receive_in_locker(self, delivery, locker_id, dimensions):
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
            result = await session.exec(
                update(DeliveryRow).where(
                    col(DeliveryRow.id) == delivery.id,
                    col(DeliveryRow.status) == DeliveryStatus.AWAITING_PICKUP.value,
                ).values(status=delivery.status.value, collected_at=_utc(delivery.collected_at),
                         returned_to_carrier_at=_utc(delivery.returned_to_carrier_at))
            )
            changed = result.rowcount == 1
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

    async def receive_in_locker(self, item, locker_id, dimensions):
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
            result = await session.exec(
                update(ReturnRow).where(
                    col(ReturnRow.id) == item.id,
                    col(ReturnRow.status) == ReturnStatus.AWAITING_CARRIER.value,
                ).values(status=item.status.value, handed_over_at=_utc(item.handed_over_at))
            )
            changed = result.rowcount == 1
            if changed:
                await _release(session, assignment, item.handed_over_at)
        return changed


def _assignment_fields(assignment, cell):
    return dict(locker_id=cell.locker_id, compartment_id=cell.id, parcel_dimensions=dimensions(assignment)) if assignment else {}


def _parcel_fk(row_type):
    return AssignmentRow.delivery_id if row_type is DeliveryRow else AssignmentRow.return_id


async def _read(sessions, row_type, convert, identifier=None):
    async with sessions() as session:
        query = select(row_type, AssignmentRow, CompartmentRow).outerjoin(AssignmentRow, _parcel_fk(row_type) == row_type.id).outerjoin(CompartmentRow, CompartmentRow.id == AssignmentRow.compartment_id)
        if identifier is not None:
            query = query.where(row_type.id == identifier)
        rows = await session.exec(query.order_by(row_type.id))
        return [convert(row, assignment, cell) for row, assignment, cell in rows]


async def _receive(sessions, entity, locker_id, parcel_dimensions, row_type):
    if entity.locker_id is not None:
        raise ValueError('Reception requires an unassigned entity')
    pending = DeliveryStatus.AWAITING_PICKUP if row_type is DeliveryRow else ReturnStatus.AWAITING_CARRIER
    if entity.status != pending:
        raise ValueError('Reception requires pending custody')
    async with sessions.begin() as session:
        cell = await choose_cell(session, locker_id, parcel_dimensions)
        values = {name: getattr(entity, name) for name in row_type.model_fields}
        values['status'] = entity.status.value
        session.add(row_type(**values))
        await session.flush()
        session.add(AssignmentRow(id=uuid4(), compartment_id=cell.id,
            delivery_id=entity.id if row_type is DeliveryRow else None,
            return_id=entity.id if row_type is ReturnRow else None,
            width_mm=parcel_dimensions.width_mm, height_mm=parcel_dimensions.height_mm,
            depth_mm=parcel_dimensions.depth_mm, assigned_at=_utc(entity.received_at)))
        await session.flush()
        result = replace(entity, locker_id=locker_id, compartment_id=cell.id, parcel_dimensions=parcel_dimensions)
    return result


async def _lock_assignment(session, row_type, identifier):
    # Lookup is nonlocking and immutable. Acquire locker lock before any parcel/assignment update.
    result = await session.exec(select(AssignmentRow, CompartmentRow.locker_id).join(CompartmentRow, CompartmentRow.id == AssignmentRow.compartment_id).where(_parcel_fk(row_type) == identifier))
    found = result.one_or_none()
    if found is None:
        return None
    assignment, locker_id = found
    await lock_locker(session, locker_id)
    # READ COMMITTED: refresh after a possible wait for the locker lock.
    await session.refresh(assignment)
    return assignment


async def _release(session, assignment, at):
    if assignment is None:
        return
    if assignment.released_at is not None:
        raise RuntimeError('Pending assigned parcel has no active assignment')
    result = await session.exec(update(AssignmentRow).where(AssignmentRow.id == assignment.id, AssignmentRow.released_at == None).values(released_at=_utc(at)))
    if result.rowcount != 1:
        raise RuntimeError('Pending assigned parcel has no active assignment')
