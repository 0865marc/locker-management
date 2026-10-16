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
from domain.lockers import Dimensions
from domain.returns import Return, ReturnStatus

RETURN_STATE = "(status = 'AWAITING_CARRIER' AND handed_over_at IS NULL) OR (status = 'HANDED_OVER' AND handed_over_at IS NOT NULL)"


_return_table = Table(
    "returns",
    SQLModel.metadata,
    Column("id", Uuid(), primary_key=True, nullable=False),
    Column("tracking_number", Text, nullable=False),
    Column("carrier_code", Text, nullable=False),
    Column("sender_name", Text),
    Column("received_at", DateTime(timezone=True), nullable=False),
    Column("status", Text, nullable=False),
    Column("handed_over_at", DateTime(timezone=True)),
    CheckConstraint(RETURN_STATE, name="ck_returns_state"),
    CheckConstraint(
        "handed_over_at IS NULL OR handed_over_at >= received_at",
        name="ck_returns_handover_time",
    ),
)


class ReturnRow(SQLModel, table=True):
    __table__: ClassVar[Table] = _return_table

    id: UUID = Field(sa_column=_return_table.c.id)
    tracking_number: str = Field(sa_column=_return_table.c.tracking_number)
    carrier_code: str = Field(sa_column=_return_table.c.carrier_code)
    sender_name: str | None = Field(default=None, sa_column=_return_table.c.sender_name)
    received_at: datetime = Field(sa_column=_return_table.c.received_at)
    status: str = Field(sa_column=_return_table.c.status)
    handed_over_at: datetime | None = Field(
        default=None, sa_column=_return_table.c.handed_over_at
    )


def _return(
    row: ReturnRow,
    assignment: AssignmentRow | None = None,
    cell: CompartmentRow | None = None,
) -> Return:
    return Return(
        locker_id=cell.locker_id
        if assignment is not None and cell is not None
        else None,
        compartment_id=cell.id if assignment is not None and cell is not None else None,
        parcel_dimensions=dimensions(assignment) if assignment is not None else None,
        id=row.id,
        tracking_number=row.tracking_number,
        carrier_code=row.carrier_code,
        sender_name=row.sender_name,
        received_at=utc_timestamp(row.received_at),
        status=ReturnStatus(row.status),
        handed_over_at=utc_timestamp(row.handed_over_at),
    )


def _row(item: Return) -> ReturnRow:
    return ReturnRow(
        id=item.id,
        tracking_number=item.tracking_number,
        carrier_code=item.carrier_code,
        sender_name=item.sender_name,
        received_at=utc_timestamp(item.received_at),
        status=item.status.value,
        handed_over_at=utc_timestamp(item.handed_over_at),
    )


class SqlModelReturnRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def save(self, item: Return) -> None:
        if item.locker_id is not None:
            raise ValueError("Use receive_in_locker for assigned receptions")
        async with self.sessions.begin() as session:
            session.add(_row(item))

    async def receive_in_locker(
        self, item: Return, locker_id: UUID, dimensions: Dimensions
    ) -> Return:
        if item.locker_id is not None:
            raise ValueError("Reception requires an unassigned entity")
        if item.status != ReturnStatus.AWAITING_CARRIER:
            raise ValueError("Reception requires pending custody")
        async with self.sessions.begin() as session:
            cell = await choose_cell(session, locker_id, dimensions)
            session.add(_row(item))
            await session.flush()
            await record_assignment(
                session, cell.id, dimensions, item.received_at, return_id=item.id
            )
            result = replace(
                item,
                locker_id=locker_id,
                compartment_id=cell.id,
                parcel_dimensions=dimensions,
            )
        return result

    async def list_all(self) -> list[Return]:
        return await self._read()

    async def get_by_id(self, identifier: UUID) -> Return | None:
        rows = await self._read(identifier)
        return rows[0] if rows else None

    async def _read(self, identifier: UUID | None = None) -> list[Return]:
        async with self.sessions() as session:
            query = (
                select(ReturnRow, AssignmentRow, CompartmentRow)
                .outerjoin(
                    AssignmentRow, col(AssignmentRow.return_id) == col(ReturnRow.id)
                )
                .outerjoin(
                    CompartmentRow,
                    col(CompartmentRow.id) == col(AssignmentRow.compartment_id),
                )
            )
            if identifier is not None:
                query = query.where(col(ReturnRow.id) == identifier)
            rows = await session.exec(query.order_by(col(ReturnRow.id)))
            return [_return(row, assignment, cell) for row, assignment, cell in rows]

    async def save_exit(self, item: Return) -> bool:
        if item.status is ReturnStatus.AWAITING_CARRIER:
            raise ValueError("A custody exit requires a terminal return")
        async with self.sessions.begin() as session:
            assignment = await lock_assignment(
                session, col(AssignmentRow.return_id), item.id
            )
            result = await SqlAlchemyAsyncSession.execute(
                session,
                update(ReturnRow)
                .where(
                    col(ReturnRow.id) == item.id,
                    col(ReturnRow.status) == ReturnStatus.AWAITING_CARRIER.value,
                )
                .values(
                    status=item.status.value,
                    handed_over_at=utc_timestamp(item.handed_over_at),
                )
                .returning(col(ReturnRow.id)),
            )
            changed = result.scalar_one_or_none() is not None
            if changed:
                await release_assignment(session, assignment, item.handed_over_at)
        return changed
