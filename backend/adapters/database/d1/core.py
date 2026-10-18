"""Strict row conversion and the shared atomic locker revision protocol."""

from collections.abc import Sequence
from datetime import datetime, timezone
from math import isfinite
from typing import cast
from uuid import UUID, uuid4

from adapters.database.d1.bindings import (
    D1BindingError,
    D1Database,
    D1PreparedStatement,
    D1Result,
    D1Row,
    D1Value,
)
from application.persistence import PersistenceError


def text(row: D1Row, key: str) -> str:
    value = row[key]
    if not isinstance(value, str):
        raise ValueError(f"Invalid D1 text column: {key}")
    return value


def optional_text(row: D1Row, key: str) -> str | None:
    return None if row[key] is None else text(row, key)


def integer(row: D1Row, key: str) -> int:
    value = row[key]
    # A float is deliberately not accepted, even if mathematically integral.
    if type(value) is not int:
        raise ValueError(f"Invalid D1 integer column: {key}")
    return value


def boolean(row: D1Row, key: str) -> bool:
    value = integer(row, key)
    if value not in (0, 1):
        raise ValueError(f"Invalid D1 boolean column: {key}")
    return bool(value)


def number(row: D1Row, key: str) -> float:
    value = row[key]
    if type(value) not in (float, int) or not isinstance(value, (float, int)):
        raise ValueError(f"Invalid D1 number column: {key}")
    return float(value)


def identifier(row: D1Row, key: str) -> UUID:
    value = text(row, key)
    result = UUID(value)
    if str(result) != value:
        raise ValueError(f"Noncanonical D1 UUID column: {key}")
    return result


def timestamp(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Timestamp must include a timezone")
    return (
        value.astimezone(timezone.utc)
        .isoformat(timespec="microseconds")
        .replace("+00:00", "Z")
    )


def optional_timestamp(value: datetime | None) -> str | None:
    return timestamp(value) if value is not None else None


def instant(row: D1Row, key: str) -> datetime:
    value = text(row, key)
    result = datetime.fromisoformat(value)
    if timestamp(result) != value:
        raise ValueError(f"Noncanonical D1 UTC column: {key}")
    return result


def optional_instant(row: D1Row, key: str) -> datetime | None:
    return None if row[key] is None else instant(row, key)


def statement(db: D1Database, sql: str, *values: D1Value) -> D1PreparedStatement:
    if len(values) > 100:
        raise ValueError("D1 parameter budget exceeded")
    if any(
        type(value) is bool
        or (type(value) is int and abs(value) > 9007199254740991)
        or (isinstance(value, float) and not isfinite(value))
        for value in values
        if isinstance(value, (int, float))
    ):
        raise ValueError("D1 numbers must be finite and integers exactly representable")
    try:
        return db.prepare(sql).bind(*values)
    except (D1BindingError, OSError) as cause:
        raise PersistenceError() from cause


async def query(db: D1Database, sql: str, *values: D1Value) -> tuple[D1Row, ...]:
    try:
        return result(await statement(db, sql, *values).all()).results
    except (D1BindingError, OSError) as cause:
        raise PersistenceError() from cause


async def execute(db: D1Database, sql: str, *values: D1Value) -> D1Result:
    try:
        return result(await statement(db, sql, *values).run())
    except (D1BindingError, OSError) as cause:
        raise PersistenceError() from cause


async def batch(
    db: D1Database, statements: Sequence[D1PreparedStatement]
) -> Sequence[D1Result]:
    try:
        raw = await db.batch(statements)
        if not isinstance(raw, (list, tuple)):
            raise PersistenceError()
        results = tuple(result(item) for item in cast(Sequence[object], raw))
    except (D1BindingError, OSError) as cause:
        # Never retry: the server may have committed before losing transport.
        raise PersistenceError() from cause
    if len(results) != len(statements):
        raise PersistenceError()
    return results


GUARD = "EXISTS (SELECT 1 FROM lockers WHERE id=? AND revision=? AND mutation_token=?)"


def guard_values(locker_id: UUID, revision: int, token: str) -> tuple[D1Value, ...]:
    return str(locker_id), revision + 1, token


def cas(
    db: D1Database,
    locker_id: UUID,
    revision: int,
    token: str,
    condition: str = "1",
    values: tuple[D1Value, ...] = (),
) -> D1PreparedStatement:
    return statement(
        db,
        "UPDATE lockers SET revision=revision+1, mutation_token=? "
        f"WHERE id=? AND revision=? AND ({condition})",
        token,
        str(locker_id),
        revision,
        *values,
    )


def mutation_token() -> str:
    return str(uuid4())


def mapping(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise PersistenceError()
    raw = cast(dict[object, object], value)
    if any(not isinstance(key, str) for key in raw):
        raise PersistenceError()
    return cast(dict[str, object], raw)


def row(value: object) -> D1Row:
    output: D1Row = {}
    for key, item in mapping(value).items():
        if (
            item is None
            or isinstance(item, str)
            or type(item) is int
            or type(item) is float
        ):
            if isinstance(item, (str, int, float)) or item is None:
                if isinstance(item, float) and not isfinite(item):
                    raise PersistenceError()
                if type(item) is int and abs(item) > 9007199254740991:
                    raise PersistenceError()
                output[key] = item
        else:
            raise PersistenceError()
    return output


def result(value: object) -> D1Result:
    raw = mapping(value)
    if raw.get("success") is not True:
        raise PersistenceError()
    metadata = mapping(raw.get("meta"))
    changes = metadata.get("changes")
    if type(changes) is not int or changes < 0:
        raise PersistenceError()
    rows = raw.get("results", [])
    if not isinstance(rows, (list, tuple)):
        raise PersistenceError()
    return D1Result(tuple(row(item) for item in cast(Sequence[object], rows)), changes)


class D1Client:
    """Validate native results without leaking raw SDK data into repositories."""

    def __init__(self, database: D1Database) -> None:
        self.database = database

    def statement(self, sql: str, *values: D1Value) -> D1PreparedStatement:
        return statement(self.database, sql, *values)

    async def query(self, sql: str, *values: D1Value) -> tuple[D1Row, ...]:
        return await query(self.database, sql, *values)

    async def execute(self, sql: str, *values: D1Value) -> D1Result:
        return await execute(self.database, sql, *values)

    async def batch(
        self, statements: Sequence[D1PreparedStatement]
    ) -> Sequence[D1Result]:
        return await batch(self.database, statements)
