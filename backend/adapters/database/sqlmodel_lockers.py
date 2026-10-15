from dataclasses import replace
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Text, UniqueConstraint, and_, text
from sqlmodel import SQLModel, Field, col, select
from domain.lockers import (Availability, AvailabilityReason as Reason, CapacityConflictError,
    Compartment, Dimensions, Locker, LockerAvailability, LockerNotFoundError, select_compartment, validate_batches)


class LockerRow(SQLModel, table=True):
    __tablename__ = 'lockers'
    id: UUID = Field(primary_key=True)
    location_id: str = Field(sa_column=Column(Text, nullable=False, index=True))
    active: bool


class CompartmentRow(SQLModel, table=True):
    __tablename__ = 'locker_compartments'
    __table_args__ = (
        CheckConstraint('width_mm BETWEEN 1 AND 2147483647 AND height_mm BETWEEN 1 AND 2147483647 AND depth_mm BETWEEN 1 AND 2147483647', name='ck_compartments_dimensions'),
        CheckConstraint('NOT (retired AND enabled)', name='ck_compartments_retired'),
    )
    id: UUID = Field(primary_key=True)
    locker_id: UUID = Field(foreign_key='lockers.id', index=True, ondelete='RESTRICT')
    width_mm: int
    height_mm: int
    depth_mm: int
    enabled: bool
    retired: bool = False


class AssignmentRow(SQLModel, table=True):
    __tablename__ = 'locker_assignments'
    __table_args__ = (
        CheckConstraint('(delivery_id IS NOT NULL AND return_id IS NULL) OR (delivery_id IS NULL AND return_id IS NOT NULL)', name='ck_assignments_parcel'),
        CheckConstraint('width_mm BETWEEN 1 AND 2147483647 AND height_mm BETWEEN 1 AND 2147483647 AND depth_mm BETWEEN 1 AND 2147483647', name='ck_assignments_dimensions'),
        CheckConstraint('released_at IS NULL OR released_at >= assigned_at', name='ck_assignments_release_time'),
        UniqueConstraint('delivery_id', name='uq_assignments_delivery'),
        UniqueConstraint('return_id', name='uq_assignments_return'),
        Index('uq_assignments_active_compartment', 'compartment_id', unique=True,
              postgresql_where=text('released_at IS NULL'), sqlite_where=text('released_at IS NULL')),
    )
    id: UUID = Field(primary_key=True)
    compartment_id: UUID = Field(foreign_key='locker_compartments.id', ondelete='RESTRICT')
    delivery_id: UUID | None = Field(default=None, foreign_key='deliveries.id', ondelete='RESTRICT')
    return_id: UUID | None = Field(default=None, foreign_key='returns.id', ondelete='RESTRICT')
    width_mm: int
    height_mm: int
    depth_mm: int
    assigned_at: datetime = Field(sa_column=Column(DateTime(timezone=True), nullable=False))
    released_at: datetime | None = Field(default=None, sa_column=Column(DateTime(timezone=True)))


def dimensions(row):
    return Dimensions(row.width_mm, row.height_mm, row.depth_mm)


def compartment(row, occupied=False):
    return Compartment(id=row.id, locker_id=row.locker_id, dimensions=dimensions(row), enabled=row.enabled, retired=row.retired, occupied=occupied)


async def lock_locker(session, identifier):
    result = await session.exec(select(LockerRow).where(LockerRow.id == identifier).with_for_update().execution_options(populate_existing=True))
    row = result.one_or_none()
    if row is None:
        raise LockerNotFoundError('Locker no encontrado')
    return row


def configuration_query():
    # A single statement gives a coherent configuration/occupancy snapshot at READ COMMITTED.
    return select(LockerRow, CompartmentRow, AssignmentRow.id).outerjoin(
        CompartmentRow, and_(CompartmentRow.locker_id == LockerRow.id, CompartmentRow.retired == False)
    ).outerjoin(AssignmentRow, and_(AssignmentRow.compartment_id == CompartmentRow.id, AssignmentRow.released_at == None))


async def configurations(session, identifier=None, location_id=None):
    query = configuration_query()
    if identifier is not None:
        query = query.where(LockerRow.id == identifier)
    if location_id is not None:
        query = query.where(LockerRow.location_id == location_id)
    result = await session.exec(query.order_by(LockerRow.id, CompartmentRow.id).execution_options(populate_existing=True))
    groups = {}
    for locker, cell, assignment_id in result:
        if locker.id not in groups:
            groups[locker.id] = [locker, []]
        if cell is not None:
            groups[locker.id][1].append(compartment(cell, assignment_id is not None))
    return [Locker(id=row.id, location_id=row.location_id, active=row.active, compartments=tuple(cells)) for row, cells in groups.values()]


def add_batches(session, identifier, batches):
    validate_batches(batches)
    for batch in batches:
        for _ in range(batch.quantity):
            session.add(CompartmentRow(id=uuid4(), locker_id=identifier, enabled=batch.enabled, retired=False,
                width_mm=batch.dimensions.width_mm, height_mm=batch.dimensions.height_mm, depth_mm=batch.dimensions.depth_mm))


async def choose_cell(session, identifier, parcel_dimensions):
    await lock_locker(session, identifier)
    locker = (await configurations(session, identifier=identifier))[0]
    if not locker.active:
        raise CapacityConflictError('LOCKER_INACTIVE')
    compatible = [c for c in locker.compartments if c.enabled and parcel_dimensions.fits_in(c.dimensions)]
    if not compatible:
        raise CapacityConflictError('NO_COMPATIBLE_CELL')
    cell = select_compartment(compatible, parcel_dimensions)
    if cell is None:
        raise CapacityConflictError('FULL')
    return cell


class SqlModelLockerRepository:
    def __init__(self, sessions):
        self.sessions = sessions

    async def create(self, location_id, batches, active=True):
        validate_batches(batches)
        locker = Locker(location_id=location_id, active=active)
        async with self.sessions.begin() as session:
            session.add(LockerRow(id=locker.id, location_id=locker.location_id, active=locker.active))
            await session.flush()
            add_batches(session, locker.id, batches)
            await session.flush()
            result = (await configurations(session, identifier=locker.id))[0]
        return result

    async def list_all(self, location_id=None):
        async with self.sessions() as session:
            return await configurations(session, location_id=location_id)

    async def get_by_id(self, identifier):
        async with self.sessions() as session:
            items = await configurations(session, identifier=identifier)
            return items[0] if items else None

    async def set_active(self, identifier, active):
        if type(active) is not bool:
            raise ValueError('active debe ser booleano')
        async with self.sessions.begin() as session:
            row = await lock_locker(session, identifier)
            row.active = active
            await session.flush()
            result = (await configurations(session, identifier=identifier))[0]
        return result

    async def add_compartments(self, identifier, batches):
        validate_batches(batches)
        async with self.sessions.begin() as session:
            await lock_locker(session, identifier)
            add_batches(session, identifier, batches)
            await session.flush()
            result = (await configurations(session, identifier=identifier))[0]
        return result

    async def _free_cell(self, session, identifier, cell_id):
        await lock_locker(session, identifier)
        row = await session.get(CompartmentRow, cell_id, populate_existing=True)
        if row is None or row.locker_id != identifier or row.retired:
            raise LockerNotFoundError('Celda no encontrada')
        occupied = (await session.exec(select(AssignmentRow.id).where(AssignmentRow.compartment_id == cell_id, AssignmentRow.released_at == None))).first()
        if occupied is not None:
            raise CapacityConflictError('CELL_OCCUPIED')
        return row

    async def update_compartment(self, identifier, cell_id, dimensions=None, enabled=None):
        if dimensions is None and enabled is None:
            raise ValueError('Se requiere un cambio')
        if enabled is not None and type(enabled) is not bool:
            raise ValueError('enabled debe ser booleano')
        async with self.sessions.begin() as session:
            row = await self._free_cell(session, identifier, cell_id)
            if dimensions is not None:
                row.width_mm, row.height_mm, row.depth_mm = dimensions.axes
            if enabled is not None:
                row.enabled = enabled
            await session.flush()
            result = compartment(row)
        return result

    async def retire_compartment(self, identifier, cell_id):
        async with self.sessions.begin() as session:
            row = await self._free_cell(session, identifier, cell_id)
            row.enabled, row.retired = False, True

    async def availability(self, location_id, dimensions):
        if not isinstance(location_id, str) or not location_id.strip():
            raise ValueError("location_id debe ser texto no vacío")
        location_id = location_id.strip()
        checked_at = datetime.now(timezone.utc)
        lockers = await self.list_all(location_id)
        results = []
        for locker in lockers:
            compatible = [c for c in locker.compartments if c.enabled and dimensions.fits_in(c.dimensions)]
            available = sum(not c.occupied for c in compatible) if locker.active else 0
            reason = Reason.LOCKER_INACTIVE if not locker.active else Reason.NO_COMPATIBLE_CELL if not compatible else Reason.AVAILABLE if available else Reason.FULL
            results.append(LockerAvailability(locker.id, locker.active, len(compatible), available, reason))
        reasons = {r.reason for r in results}
        reason = next((r for r in (Reason.AVAILABLE, Reason.FULL, Reason.NO_COMPATIBLE_CELL, Reason.LOCKER_INACTIVE) if r in reasons), Reason.NO_LOCKER)
        return Availability(location_id, dimensions, checked_at, reason, tuple(results))
