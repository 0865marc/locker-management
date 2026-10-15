from typing import ClassVar, cast
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import Boolean, ForeignKey, Integer, Table, Uuid, CheckConstraint, Column, DateTime, Double, Index, Text, UniqueConstraint, and_, text
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel.sql.expression import Select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlmodel import SQLModel, Field, col, select
from domain.lockers import (Availability, AvailabilityReason as Reason, CapacityConflictError,
    Address, Coordinates, LockerPatch, CompartmentBatch, location_alias, Compartment, Dimensions, Locker, LockerAvailability, LockerNotFoundError, select_compartment, validate_batches)


ADDRESS_PRESENT = "country_code IS NOT NULL AND postal_code IS NOT NULL AND province IS NOT NULL AND city IS NOT NULL AND street IS NOT NULL AND street_number IS NOT NULL"
ADDRESS_ABSENT = "country_code IS NULL AND postal_code IS NULL AND province IS NULL AND city IS NULL AND street IS NULL AND street_number IS NULL"
# btrim uses the exact Unicode whitespace set recognized by Python str.strip().
WHITESPACE_SQL = "U&'\\0009\\000a\\000b\\000c\\000d\\001c\\001d\\001e\\001f\\0020\\0085\\00a0\\1680\\2000\\2001\\2002\\2003\\2004\\2005\\2006\\2007\\2008\\2009\\200a\\2028\\2029\\202f\\205f\\3000'"
ADDRESS_VALID = "country_code = 'ES' AND postal_code ~ '^[0-9]{5}$' AND " + ' AND '.join(
    f"btrim({name}, {WHITESPACE_SQL}) <> '' AND {name} = btrim({name}, {WHITESPACE_SQL})"
    for name in ('province', 'city', 'street', 'street_number')
)
ADDRESS_CHECK = f"({ADDRESS_ABSENT}) OR (({ADDRESS_PRESENT}) AND ({ADDRESS_VALID}))"
COORDINATES_CHECK = "(latitude IS NULL AND longitude IS NULL) OR (latitude IS NOT NULL AND longitude IS NOT NULL AND latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)"


_locker_table = Table(
    'lockers', SQLModel.metadata,
    Column('id', Uuid(), primary_key=True, nullable=False),
    Column('location_id', Text, nullable=True, index=True),
    Column('active', Boolean(), nullable=False),
    Column('country_code', Text),
    Column('postal_code', Text),
    Column('province', Text),
    Column('city', Text),
    Column('street', Text),
    Column('street_number', Text),
    Column('latitude', Double),
    Column('longitude', Double),
    CheckConstraint(ADDRESS_CHECK, name='ck_lockers_address'),
    CheckConstraint(COORDINATES_CHECK, name='ck_lockers_coordinates'),
)


class LockerRow(SQLModel, table=True):
    __table__: ClassVar[Table] = _locker_table

    id: UUID = Field(sa_column=_locker_table.c.id)
    location_id: str | None = Field(default=None, sa_column=_locker_table.c.location_id)
    active: bool = Field(sa_column=_locker_table.c.active)
    country_code: str | None = Field(default=None, sa_column=_locker_table.c.country_code)
    postal_code: str | None = Field(default=None, sa_column=_locker_table.c.postal_code)
    province: str | None = Field(default=None, sa_column=_locker_table.c.province)
    city: str | None = Field(default=None, sa_column=_locker_table.c.city)
    street: str | None = Field(default=None, sa_column=_locker_table.c.street)
    street_number: str | None = Field(default=None, sa_column=_locker_table.c.street_number)
    latitude: float | None = Field(default=None, sa_column=_locker_table.c.latitude)
    longitude: float | None = Field(default=None, sa_column=_locker_table.c.longitude)


_compartment_table = Table(
    'locker_compartments', SQLModel.metadata,
    Column('id', Uuid(), primary_key=True, nullable=False),
    Column('locker_id', Uuid(), ForeignKey('lockers.id', ondelete='RESTRICT'), index=True, nullable=False),
    Column('width_mm', Integer(), nullable=False),
    Column('height_mm', Integer(), nullable=False),
    Column('depth_mm', Integer(), nullable=False),
    Column('enabled', Boolean(), nullable=False),
    Column('retired', Boolean(), nullable=False, default=False),
    CheckConstraint('width_mm BETWEEN 1 AND 2147483647 AND height_mm BETWEEN 1 AND 2147483647 AND depth_mm BETWEEN 1 AND 2147483647', name='ck_compartments_dimensions'),
    CheckConstraint('NOT (retired AND enabled)', name='ck_compartments_retired'),
)


class CompartmentRow(SQLModel, table=True):
    __table__: ClassVar[Table] = _compartment_table

    id: UUID = Field(sa_column=_compartment_table.c.id)
    locker_id: UUID = Field(sa_column=_compartment_table.c.locker_id)
    width_mm: int = Field(sa_column=_compartment_table.c.width_mm)
    height_mm: int = Field(sa_column=_compartment_table.c.height_mm)
    depth_mm: int = Field(sa_column=_compartment_table.c.depth_mm)
    enabled: bool = Field(sa_column=_compartment_table.c.enabled)
    retired: bool = Field(default=False, sa_column=_compartment_table.c.retired)


_assignment_table = Table(
    'locker_assignments', SQLModel.metadata,
    Column('id', Uuid(), primary_key=True, nullable=False),
    Column('compartment_id', Uuid(), ForeignKey('locker_compartments.id', ondelete='RESTRICT'), nullable=False),
    Column('delivery_id', Uuid(), ForeignKey('deliveries.id', ondelete='RESTRICT'), nullable=True),
    Column('return_id', Uuid(), ForeignKey('returns.id', ondelete='RESTRICT'), nullable=True),
    Column('width_mm', Integer(), nullable=False),
    Column('height_mm', Integer(), nullable=False),
    Column('depth_mm', Integer(), nullable=False),
    Column('assigned_at', DateTime(timezone=True), nullable=False),
    Column('released_at', DateTime(timezone=True)),
    CheckConstraint('(delivery_id IS NOT NULL AND return_id IS NULL) OR (delivery_id IS NULL AND return_id IS NOT NULL)', name='ck_assignments_parcel'),
    CheckConstraint('width_mm BETWEEN 1 AND 2147483647 AND height_mm BETWEEN 1 AND 2147483647 AND depth_mm BETWEEN 1 AND 2147483647', name='ck_assignments_dimensions'),
    CheckConstraint('released_at IS NULL OR released_at >= assigned_at', name='ck_assignments_release_time'),
    UniqueConstraint('delivery_id', name='uq_assignments_delivery'),
    UniqueConstraint('return_id', name='uq_assignments_return'),
    Index('uq_assignments_active_compartment', 'compartment_id', unique=True, postgresql_where=text('released_at IS NULL')),
)


class AssignmentRow(SQLModel, table=True):
    __table__: ClassVar[Table] = _assignment_table

    id: UUID = Field(sa_column=_assignment_table.c.id)
    compartment_id: UUID = Field(sa_column=_assignment_table.c.compartment_id)
    delivery_id: UUID | None = Field(default=None, sa_column=_assignment_table.c.delivery_id)
    return_id: UUID | None = Field(default=None, sa_column=_assignment_table.c.return_id)
    width_mm: int = Field(sa_column=_assignment_table.c.width_mm)
    height_mm: int = Field(sa_column=_assignment_table.c.height_mm)
    depth_mm: int = Field(sa_column=_assignment_table.c.depth_mm)
    assigned_at: datetime = Field(sa_column=_assignment_table.c.assigned_at)
    released_at: datetime | None = Field(default=None, sa_column=_assignment_table.c.released_at)


def dimensions(row: CompartmentRow | AssignmentRow) -> Dimensions:
    return Dimensions(row.width_mm, row.height_mm, row.depth_mm)


def compartment(row: CompartmentRow, occupied: bool = False) -> Compartment:
    return Compartment(id=row.id, locker_id=row.locker_id, dimensions=dimensions(row), enabled=row.enabled, retired=row.retired, occupied=occupied)


async def lock_locker(session: AsyncSession, identifier: UUID) -> LockerRow:
    result = await session.exec(select(LockerRow).where(col(LockerRow.id) == identifier).with_for_update().execution_options(populate_existing=True))
    row = result.one_or_none()
    if row is None:
        raise LockerNotFoundError('Locker no encontrado')
    return row


def configuration_query() -> Select[LockerRow, CompartmentRow | None, UUID | None]:
    # A single statement gives a coherent configuration/occupancy snapshot at READ COMMITTED.
    # SQLModel does not infer the nullable entities introduced by LEFT OUTER JOIN.
    statement = select(LockerRow, CompartmentRow, col(AssignmentRow.id)).outerjoin(
        CompartmentRow, and_(col(CompartmentRow.locker_id) == col(LockerRow.id), col(CompartmentRow.retired) == False)
    ).outerjoin(AssignmentRow, and_(col(AssignmentRow.compartment_id) == col(CompartmentRow.id), col(AssignmentRow.released_at) == None))
    return cast(Select[LockerRow, CompartmentRow | None, UUID | None], statement)


async def configurations(session: AsyncSession, identifier: UUID | None = None, location_id: str | None = None) -> list[Locker]:
    query = configuration_query()
    if identifier is not None:
        query = query.where(col(LockerRow.id) == identifier)
    if location_id is not None:
        query = query.where(col(LockerRow.location_id) == location_id)
    result = await session.exec(query.order_by(col(LockerRow.id), col(CompartmentRow.id)).execution_options(populate_existing=True))
    groups: dict[UUID, tuple[LockerRow, list[Compartment]]] = {}
    for locker, cell, assignment_id in result:
        if locker.id not in groups:
            groups[locker.id] = (locker, [])
        if cell is not None:
            groups[locker.id][1].append(compartment(cell, assignment_id is not None))
    return [Locker(id=row.id, location_id=row.location_id, active=row.active, compartments=tuple(cells), address=address_value(row), coordinates=coordinates_value(row)) for row, cells in groups.values()]


def add_batches(session: AsyncSession, identifier: UUID, batches: list[CompartmentBatch]) -> None:
    validate_batches(batches)
    for batch in batches:
        for _ in range(batch.quantity):
            session.add(CompartmentRow(id=uuid4(), locker_id=identifier, enabled=batch.enabled, retired=False,
                width_mm=batch.dimensions.width_mm, height_mm=batch.dimensions.height_mm, depth_mm=batch.dimensions.depth_mm))


async def choose_cell(session: AsyncSession, identifier: UUID, parcel_dimensions: Dimensions) -> Compartment:
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
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def create(self, location_id: str | None, batches: list[CompartmentBatch], active: bool = True, address: Address | None = None, coordinates: Coordinates | None = None) -> Locker:
        validate_batches(batches)
        locker = Locker(location_id=location_id, active=active, address=address, coordinates=coordinates)
        if locker.location_id is None and address is None:
            raise ValueError("Se requiere location_id o address")
        async with self.sessions.begin() as session:
            row = LockerRow(id=locker.id, location_id=locker.location_id, active=locker.active)
            apply_geography(row, address, coordinates)
            session.add(row)
            await session.flush()
            add_batches(session, locker.id, batches)
            await session.flush()
            result = (await configurations(session, identifier=locker.id))[0]
        return result

    async def list_all(self, location_id: str | None = None) -> list[Locker]:
        async with self.sessions() as session:
            return await configurations(session, location_id=location_id)

    async def get_by_id(self, identifier: UUID) -> Locker | None:
        async with self.sessions() as session:
            items = await configurations(session, identifier=identifier)
            return items[0] if items else None

    async def set_active(self, identifier: UUID, active: bool) -> Locker:
        return await self.update(identifier, LockerPatch(active=active))

    async def update(self, identifier: UUID, patch: LockerPatch) -> Locker:
        async with self.sessions.begin() as session:
            row = await lock_locker(session, identifier)
            if patch.active is not None:
                row.active = patch.active
            if patch.address_supplied:
                apply_address(row, patch.address)
            if patch.coordinates_supplied:
                apply_coordinates(row, patch.coordinates)
            await session.flush()
            result = (await configurations(session, identifier=identifier))[0]
        return result

    async def add_compartments(self, identifier: UUID, batches: list[CompartmentBatch]) -> Locker:
        validate_batches(batches)
        async with self.sessions.begin() as session:
            await lock_locker(session, identifier)
            add_batches(session, identifier, batches)
            await session.flush()
            result = (await configurations(session, identifier=identifier))[0]
        return result

    async def _free_cell(self, session: AsyncSession, identifier: UUID, cell_id: UUID) -> CompartmentRow:
        await lock_locker(session, identifier)
        row = await session.get(CompartmentRow, cell_id, populate_existing=True)
        if row is None or row.locker_id != identifier or row.retired:
            raise LockerNotFoundError('Celda no encontrada')
        occupied = (await session.exec(select(col(AssignmentRow.id)).where(col(AssignmentRow.compartment_id) == cell_id, col(AssignmentRow.released_at) == None))).first()
        if occupied is not None:
            raise CapacityConflictError('CELL_OCCUPIED')
        return row

    async def update_compartment(self, identifier: UUID, cell_id: UUID, dimensions: Dimensions | None = None, enabled: bool | None = None) -> Compartment:
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

    async def retire_compartment(self, identifier: UUID, cell_id: UUID) -> None:
        async with self.sessions.begin() as session:
            row = await self._free_cell(session, identifier, cell_id)
            row.enabled, row.retired = False, True

    async def availability(self, location_id: str, dimensions: Dimensions) -> Availability:
        location_id = location_alias(location_id)
        checked_at = datetime.now(timezone.utc)
        lockers = await self.list_all(location_id)
        results: list[LockerAvailability] = []
        for locker in lockers:
            compatible = [c for c in locker.compartments if c.enabled and dimensions.fits_in(c.dimensions)]
            available = sum(not c.occupied for c in compatible) if locker.active else 0
            reason = Reason.LOCKER_INACTIVE if not locker.active else Reason.NO_COMPATIBLE_CELL if not compatible else Reason.AVAILABLE if available else Reason.FULL
            results.append(LockerAvailability(locker.id, locker.active, len(compatible), available, reason))
        reasons = {r.reason for r in results}
        reason = next((r for r in (Reason.AVAILABLE, Reason.FULL, Reason.NO_COMPATIBLE_CELL, Reason.LOCKER_INACTIVE) if r in reasons), Reason.NO_LOCKER)
        return Availability(location_id, dimensions, checked_at, reason, tuple(results))


def address_value(row: LockerRow) -> Address | None:
    values = (row.country_code, row.postal_code, row.province, row.city, row.street, row.street_number)
    if all(value is None for value in values):
        return None
    if row.country_code is None or row.postal_code is None or row.province is None or row.city is None or row.street is None or row.street_number is None:
        raise RuntimeError('Persisted address is incomplete')
    return Address(row.country_code, row.postal_code, row.province, row.city, row.street, row.street_number)


def coordinates_value(row: LockerRow) -> Coordinates | None:
    if row.latitude is None and row.longitude is None:
        return None
    if row.latitude is None or row.longitude is None:
        raise RuntimeError('Persisted coordinates are incomplete')
    return Coordinates(row.latitude, row.longitude)


def apply_address(row: LockerRow, address: Address | None) -> None:
    row.country_code = address.country_code if address else None
    row.postal_code = address.postal_code if address else None
    row.province = address.province if address else None
    row.city = address.city if address else None
    row.street = address.street if address else None
    row.street_number = address.street_number if address else None


def apply_coordinates(row: LockerRow, coordinates: Coordinates | None) -> None:
    row.latitude = coordinates.latitude if coordinates else None
    row.longitude = coordinates.longitude if coordinates else None


def apply_geography(row: LockerRow, address: Address | None, coordinates: Coordinates | None) -> None:
    apply_address(row, address)
    apply_coordinates(row, coordinates)
