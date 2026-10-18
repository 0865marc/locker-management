"""Atomic parcel/assignment changes used by both custody flows."""

from typing import Literal
from uuid import UUID, uuid4

from adapters.database.d1.bindings import D1Database, D1Provider, D1Row, D1Value
from adapters.database.d1.core import (
    GUARD,
    batch,
    cas,
    execute,
    guard_values,
    identifier,
    integer,
    mutation_token,
    query,
    statement,
    text,
)
from adapters.database.d1.selection import select
from application.persistence import PersistenceError
from domain.lockers import Dimensions


class CustodyStore:
    def __init__(
        self,
        provider: D1Provider,
        table: Literal["deliveries", "returns"],
        columns: tuple[str, ...],
        pending: str,
    ) -> None:
        self.provider = provider
        self.table = table
        self.columns = columns
        self.pending = pending
        self.parcel_fk = "delivery_id" if table == "deliveries" else "return_id"

    def insert(
        self,
        db: D1Database,
        values: tuple[D1Value, ...],
        guard: tuple[D1Value, ...] | None = None,
    ):
        sql = f"INSERT INTO {self.table} ({','.join(self.columns)}) SELECT {','.join('?' for _ in values)}"
        return statement(
            db, sql + (" WHERE " + GUARD if guard else ""), *values, *(guard or ())
        )

    async def save(self, values: tuple[D1Value, ...]) -> None:
        db = self.provider()
        await batch(db, [self.insert(db, values)])

    async def read(self, parcel_id: UUID | None = None) -> tuple[D1Row, ...]:
        return await query(
            self.provider(),
            f"""SELECT p.*,c.locker_id,a.compartment_id,
        a.width_mm AS parcel_width,a.height_mm AS parcel_height,a.depth_mm AS parcel_depth
        FROM {self.table} p LEFT JOIN locker_assignments a ON a.{self.parcel_fk}=p.id
        LEFT JOIN locker_compartments c ON c.id=a.compartment_id"""
            + (" WHERE p.id=?" if parcel_id is not None else "")
            + " ORDER BY p.id",
            *((str(parcel_id),) if parcel_id is not None else ()),
        )

    async def receive(
        self,
        parcel_id: UUID,
        values: tuple[D1Value, ...],
        locker_id: UUID,
        dimensions: Dimensions,
        assigned_at: str,
    ) -> UUID:
        db = self.provider()
        for _ in range(3):
            selection = await select(db, locker_id, dimensions)
            token = mutation_token()
            guard = guard_values(locker_id, selection.revision, token)
            results = await batch(
                db,
                [
                    cas(db, locker_id, selection.revision, token),
                    self.insert(db, values, guard),
                    statement(
                        db,
                        f"""INSERT INTO locker_assignments
                (id,compartment_id,{self.parcel_fk},width_mm,height_mm,depth_mm,assigned_at)
                SELECT ?,?,?,?,?,?,? WHERE """
                        + GUARD,
                        str(uuid4()),
                        str(selection.compartment_id),
                        str(parcel_id),
                        *dimensions.axes,
                        assigned_at,
                        *guard,
                    ),
                ],
            )
            if results[0].changes == 0:
                continue
            if results[0].changes != 1:
                raise PersistenceError()
            return selection.compartment_id
        raise PersistenceError()

    async def exit(
        self,
        parcel_id: UUID,
        columns: tuple[str, ...],
        values: tuple[D1Value, ...],
        at: str,
    ) -> bool:
        db = self.provider()
        changes = ",".join(f"{column}=?" for column in columns)
        for _ in range(3):
            rows = await query(
                db,
                f"""SELECT p.status,a.id AS assignment_id,a.released_at,
            c.locker_id,l.revision FROM {self.table} p
            LEFT JOIN locker_assignments a ON a.{self.parcel_fk}=p.id
            LEFT JOIN locker_compartments c ON c.id=a.compartment_id
            LEFT JOIN lockers l ON l.id=c.locker_id WHERE p.id=?""",
                str(parcel_id),
            )
            if not rows or text(rows[0], "status") != self.pending:
                return False
            row = rows[0]
            if row["assignment_id"] is None:
                result = await execute(
                    db,
                    f"UPDATE {self.table} SET {changes} WHERE id=? AND status=?",
                    *values,
                    str(parcel_id),
                    self.pending,
                )
                return result.changes == 1
            if row["released_at"] is not None:
                raise PersistenceError()
            locker_id = identifier(row, "locker_id")
            assignment_id = identifier(row, "assignment_id")
            revision = integer(row, "revision")
            token = mutation_token()
            guard = guard_values(locker_id, revision, token)
            condition = f"""EXISTS (SELECT 1 FROM {self.table} p JOIN locker_assignments a
            ON a.{self.parcel_fk}=p.id WHERE p.id=? AND p.status=? AND a.id=? AND a.released_at IS NULL)"""
            results = await batch(
                db,
                [
                    cas(
                        db,
                        locker_id,
                        revision,
                        token,
                        condition,
                        (str(parcel_id), self.pending, str(assignment_id)),
                    ),
                    statement(
                        db,
                        f"UPDATE {self.table} SET {changes} WHERE id=? AND status=? AND "
                        + GUARD,
                        *values,
                        str(parcel_id),
                        self.pending,
                        *guard,
                    ),
                    statement(
                        db,
                        "UPDATE locker_assignments SET released_at=? WHERE id=? AND released_at IS NULL AND "
                        + GUARD,
                        at,
                        str(assignment_id),
                        *guard,
                    ),
                ],
            )
            if results[0].changes == 0:
                continue
            if results[0].changes != 1:
                raise PersistenceError()
            return True
        raise PersistenceError()


def assignment(row: D1Row) -> tuple[UUID | None, UUID | None, Dimensions | None]:
    if row["locker_id"] is None:
        return None, None, None
    return (
        identifier(row, "locker_id"),
        identifier(row, "compartment_id"),
        Dimensions(
            integer(row, "parcel_width"),
            integer(row, "parcel_height"),
            integer(row, "parcel_depth"),
        ),
    )
