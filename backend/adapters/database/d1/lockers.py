"""D1 configuration and custody concurrency share a revision and fresh token."""

import json
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from uuid import UUID, uuid4

from adapters.database.d1.bindings import (
    D1Database,
    D1PreparedStatement,
    D1Provider,
    D1Row,
    D1Value,
)
from adapters.database.d1.core import (
    GUARD,
    batch,
    boolean,
    cas,
    guard_values,
    identifier,
    integer,
    mutation_token,
    number,
    optional_text,
    query,
    statement,
    text,
)
from application.persistence import PersistenceError
from domain.lockers import (
    Address,
    Availability,
    CapacityConflictError,
    Compartment,
    CompartmentBatch,
    Coordinates,
    Dimensions,
    Locker,
    LockerAvailability,
    LockerNotFoundError,
    LockerPatch,
    location_alias,
    select_compartment,
    validate_batches,
)
from domain.lockers import (
    AvailabilityReason as Reason,
)

CONFIGURATION = """SELECT l.*, c.id AS cell_id, c.width_mm, c.height_mm,
 c.depth_mm, c.enabled, c.retired, a.id AS assignment_id
 FROM lockers l LEFT JOIN locker_compartments c
 ON c.locker_id=l.id AND c.retired=0
 LEFT JOIN locker_assignments a ON a.compartment_id=c.id AND a.released_at IS NULL"""


@dataclass(frozen=True)
class Snapshot:
    locker: Locker
    revision: int


def geography(
    address: Address | None, coordinates: Coordinates | None
) -> tuple[D1Value, ...]:
    return (
        address.country_code if address else None,
        address.postal_code if address else None,
        address.province if address else None,
        address.city if address else None,
        address.street if address else None,
        address.street_number if address else None,
        coordinates.latitude if coordinates else None,
        coordinates.longitude if coordinates else None,
    )


def configurations(rows: tuple[D1Row, ...]) -> list[Snapshot]:
    groups: dict[UUID, tuple[D1Row, list[Compartment]]] = {}
    for row in rows:
        key = identifier(row, "id")
        if key not in groups:
            groups[key] = row, []
        if row["cell_id"] is not None:
            groups[key][1].append(
                Compartment(
                    id=identifier(row, "cell_id"),
                    locker_id=key,
                    dimensions=Dimensions(
                        integer(row, "width_mm"),
                        integer(row, "height_mm"),
                        integer(row, "depth_mm"),
                    ),
                    enabled=boolean(row, "enabled"),
                    retired=boolean(row, "retired"),
                    occupied=row["assignment_id"] is not None,
                )
            )
    result: list[Snapshot] = []
    for key, (row, cells) in groups.items():
        address = (
            None
            if row["country_code"] is None
            else Address(
                text(row, "country_code"),
                text(row, "postal_code"),
                text(row, "province"),
                text(row, "city"),
                text(row, "street"),
                text(row, "street_number"),
            )
        )
        coordinates = (
            None
            if row["latitude"] is None
            else Coordinates(number(row, "latitude"), number(row, "longitude"))
        )
        result.append(
            Snapshot(
                Locker(
                    id=key,
                    location_id=optional_text(row, "location_id"),
                    active=boolean(row, "active"),
                    compartments=tuple(cells),
                    address=address,
                    coordinates=coordinates,
                ),
                integer(row, "revision"),
            )
        )
    return result


async def snapshot(db: D1Database, locker_id: UUID) -> Snapshot:
    items = configurations(
        await query(db, CONFIGURATION + " WHERE l.id=? ORDER BY c.id", str(locker_id))
    )
    if not items:
        raise LockerNotFoundError("Locker no encontrado")
    return items[0]


def choose_cell(state: Snapshot, dimensions: Dimensions) -> Compartment:
    locker = state.locker
    if not locker.active:
        raise CapacityConflictError("LOCKER_INACTIVE")
    compatible = [
        c for c in locker.compartments if c.enabled and dimensions.fits_in(c.dimensions)
    ]
    if not compatible:
        raise CapacityConflictError("NO_COMPATIBLE_CELL")
    cell = select_compartment(compatible, dimensions)
    if cell is None:
        raise CapacityConflictError("FULL")
    return cell


def cells_json(batches: list[CompartmentBatch]) -> str:
    validate_batches(batches)
    return json.dumps(
        [
            {
                "id": str(uuid4()),
                "width_mm": b.dimensions.width_mm,
                "height_mm": b.dimensions.height_mm,
                "depth_mm": b.dimensions.depth_mm,
                "enabled": int(b.enabled),
            }
            for b in batches
            for _ in range(b.quantity)
        ],
        separators=(",", ":"),
    )


def insert_cells(
    db: D1Database,
    locker_id: UUID,
    payload: str,
    revision: int | None = None,
    token: str | None = None,
) -> D1PreparedStatement:
    sql = """INSERT INTO locker_compartments
    (id,locker_id,width_mm,height_mm,depth_mm,enabled,retired)
    SELECT json_extract(value,'$.id'), ?, json_extract(value,'$.width_mm'),
    json_extract(value,'$.height_mm'), json_extract(value,'$.depth_mm'),
    json_extract(value,'$.enabled'), 0 FROM json_each(?)"""
    if revision is None:
        return statement(db, sql, str(locker_id), payload)
    if token is None:
        raise ValueError("Guard token required")
    return statement(
        db,
        sql + " WHERE " + GUARD,
        str(locker_id),
        payload,
        *guard_values(locker_id, revision, token),
    )


def response_statement(
    db: D1Database, locker_id: UUID, revision: int, token: str
) -> D1PreparedStatement:
    return statement(
        db,
        CONFIGURATION
        + " WHERE l.id=? AND l.revision=? AND l.mutation_token=? ORDER BY c.id",
        *guard_values(locker_id, revision, token),
    )


Mutation = Callable[[D1Database, Snapshot, str], list[D1PreparedStatement]]


class D1LockerRepository:
    def __init__(self, provider: D1Provider) -> None:
        self.provider = provider

    async def create(
        self,
        location_id: str | None,
        batches: list[CompartmentBatch],
        active: bool = True,
        address: Address | None = None,
        coordinates: Coordinates | None = None,
    ) -> Locker:
        payload = cells_json(batches)
        locker = Locker(
            location_id=location_id,
            active=active,
            address=address,
            coordinates=coordinates,
        )
        if locker.location_id is None and address is None:
            raise ValueError("Se requiere location_id o address")
        db = self.provider()
        results = await batch(
            db,
            [
                statement(
                    db,
                    """INSERT INTO lockers
            (id,location_id,active,country_code,postal_code,province,city,street,street_number,latitude,longitude)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    str(locker.id),
                    locker.location_id,
                    int(active),
                    *geography(address, coordinates),
                ),
                insert_cells(db, locker.id, payload),
                statement(
                    db, CONFIGURATION + " WHERE l.id=? ORDER BY c.id", str(locker.id)
                ),
            ],
        )
        return configurations(results[-1].results)[0].locker

    async def list_all(self, location_id: str | None = None) -> list[Locker]:
        db = self.provider()
        rows = await query(
            db,
            CONFIGURATION
            + (" WHERE l.location_id=?" if location_id is not None else "")
            + " ORDER BY l.id,c.id",
            *((location_id,) if location_id is not None else ()),
        )
        return [state.locker for state in configurations(rows)]

    async def get_by_id(self, identifier: UUID) -> Locker | None:
        items = configurations(
            await query(
                self.provider(),
                CONFIGURATION + " WHERE l.id=? ORDER BY c.id",
                str(identifier),
            )
        )
        return items[0].locker if items else None

    async def _mutate(self, locker_id: UUID, operation: Mutation) -> Locker:
        db = self.provider()
        for _ in range(3):
            state = await snapshot(db, locker_id)
            token = mutation_token()
            writes = operation(db, state, token)
            results = await batch(
                db,
                [
                    cas(db, locker_id, state.revision, token),
                    *writes,
                    response_statement(db, locker_id, state.revision, token),
                ],
            )
            if results[0].changes == 0:
                continue
            if results[0].changes != 1:
                raise PersistenceError()
            return configurations(results[-1].results)[0].locker
        raise PersistenceError()

    async def set_active(self, identifier: UUID, active: bool) -> Locker:
        return await self.update(identifier, LockerPatch(active=active))

    async def update(self, identifier: UUID, patch: LockerPatch) -> Locker:
        def operation(
            db: D1Database, state: Snapshot, token: str
        ) -> list[D1PreparedStatement]:
            locker = state.locker
            active = locker.active if patch.active is None else patch.active
            address = patch.address if patch.address_supplied else locker.address
            coordinates = (
                patch.coordinates if patch.coordinates_supplied else locker.coordinates
            )
            return [
                statement(
                    db,
                    """UPDATE lockers SET active=?,country_code=?,postal_code=?,
            province=?,city=?,street=?,street_number=?,latitude=?,longitude=? WHERE id=? AND """
                    + GUARD,
                    int(active),
                    *geography(address, coordinates),
                    str(identifier),
                    *guard_values(identifier, state.revision, token),
                )
            ]

        return await self._mutate(identifier, operation)

    async def add_compartments(
        self, identifier: UUID, batches: list[CompartmentBatch]
    ) -> Locker:
        payload = cells_json(batches)

        def operation(
            db: D1Database, state: Snapshot, token: str
        ) -> list[D1PreparedStatement]:
            return [insert_cells(db, identifier, payload, state.revision, token)]

        return await self._mutate(identifier, operation)

    async def _change_cell(
        self,
        identifier: UUID,
        cell_id: UUID,
        dimensions: Dimensions | None,
        enabled: bool | None,
        retired: bool,
    ) -> Locker:
        def operation(
            db: D1Database, state: Snapshot, token: str
        ) -> list[D1PreparedStatement]:
            cell = next((c for c in state.locker.compartments if c.id == cell_id), None)
            if cell is None:
                raise LockerNotFoundError("Celda no encontrada")
            if cell.occupied:
                raise CapacityConflictError("CELL_OCCUPIED")
            changed = replace(
                cell,
                dimensions=dimensions or cell.dimensions,
                enabled=False
                if retired
                else cell.enabled
                if enabled is None
                else enabled,
                retired=retired,
            )
            return [
                statement(
                    db,
                    """UPDATE locker_compartments SET width_mm=?,height_mm=?,depth_mm=?,
            enabled=?,retired=? WHERE id=? AND locker_id=? AND """
                    + GUARD,
                    *changed.dimensions.axes,
                    int(changed.enabled),
                    int(changed.retired),
                    str(cell_id),
                    str(identifier),
                    *guard_values(identifier, state.revision, token),
                )
            ]

        return await self._mutate(identifier, operation)

    async def update_compartment(
        self,
        identifier: UUID,
        cell_id: UUID,
        dimensions: Dimensions | None = None,
        enabled: bool | None = None,
    ) -> Compartment:
        if dimensions is None and enabled is None:
            raise ValueError("Se requiere un cambio")
        if enabled is not None and type(enabled) is not bool:
            raise ValueError("enabled debe ser booleano")
        locker = await self._change_cell(
            identifier, cell_id, dimensions, enabled, False
        )
        return next(c for c in locker.compartments if c.id == cell_id)

    async def retire_compartment(self, identifier: UUID, cell_id: UUID) -> None:
        await self._change_cell(identifier, cell_id, None, None, True)

    async def availability(
        self, location_id: str, dimensions: Dimensions
    ) -> Availability:
        location_id = location_alias(location_id)
        checked_at = datetime.now(timezone.utc)
        results: list[LockerAvailability] = []
        for locker in await self.list_all(location_id):
            compatible = [
                c
                for c in locker.compartments
                if c.enabled and dimensions.fits_in(c.dimensions)
            ]
            available = sum(not c.occupied for c in compatible) if locker.active else 0
            reason = (
                Reason.LOCKER_INACTIVE
                if not locker.active
                else Reason.NO_COMPATIBLE_CELL
                if not compatible
                else Reason.AVAILABLE
                if available
                else Reason.FULL
            )
            results.append(
                LockerAvailability(
                    locker.id, locker.active, len(compatible), available, reason
                )
            )
        reasons = {r.reason for r in results}
        reason = next(
            (
                r
                for r in (
                    Reason.AVAILABLE,
                    Reason.FULL,
                    Reason.NO_COMPATIBLE_CELL,
                    Reason.LOCKER_INACTIVE,
                )
                if r in reasons
            ),
            Reason.NO_LOCKER,
        )
        return Availability(location_id, dimensions, checked_at, reason, tuple(results))
