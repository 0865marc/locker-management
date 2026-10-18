"""One coherent custody decision; exact volume keys never cross the D1 boundary."""

from dataclasses import dataclass
from uuid import UUID

from adapters.database.d1.bindings import D1Database
from adapters.database.d1.core import boolean, identifier, integer, query
from domain.lockers import CapacityConflictError, Dimensions, LockerNotFoundError

# B=2^31: volume=high*B+low. Each intermediate product stays below 2^62.
# Never replace this with SQLite's overflowing triple product, or return high
# across the JavaScript boundary where integers above 2^53 lose precision.
SELECTION = """WITH requested AS (
    SELECT id, active, revision FROM lockers WHERE id=?
), compatible AS (
    SELECT c.id, c.width_mm*c.height_mm AS product, c.depth_mm AS depth
    FROM locker_compartments c JOIN requested l ON c.locker_id=l.id
    WHERE c.enabled=1 AND c.retired=0
      AND min(c.width_mm,c.height_mm,c.depth_mm)>=?
      AND c.width_mm+c.height_mm+c.depth_mm
          -min(c.width_mm,c.height_mm,c.depth_mm)
          -max(c.width_mm,c.height_mm,c.depth_mm)>=?
      AND max(c.width_mm,c.height_mm,c.depth_mm)>=?
), split AS (
    SELECT id, product, depth, (product & 2147483647)*depth AS remainder
    FROM compatible
), volumes AS (
    SELECT id, (product >> 31)*depth+(remainder >> 31) AS high,
           remainder & 2147483647 AS low
    FROM split
)
SELECT l.id, l.active, l.revision,
       EXISTS (SELECT 1 FROM compatible) AS has_compatible,
       (SELECT v.id FROM volumes v
        WHERE NOT EXISTS (
            SELECT 1 FROM locker_assignments a
            WHERE a.compartment_id=v.id AND a.released_at IS NULL
        )
        ORDER BY v.high,v.low,v.id COLLATE BINARY LIMIT 1) AS candidate_id
FROM requested l"""


@dataclass(frozen=True)
class Selection:
    revision: int
    compartment_id: UUID


async def select(db: D1Database, locker_id: UUID, dimensions: Dimensions) -> Selection:
    rows = await query(db, SELECTION, str(locker_id), *sorted(dimensions.axes))
    if not rows:
        raise LockerNotFoundError("Locker no encontrado")
    row = rows[0]
    if not boolean(row, "active"):
        raise CapacityConflictError("LOCKER_INACTIVE")
    if not boolean(row, "has_compatible"):
        raise CapacityConflictError("NO_COMPATIBLE_CELL")
    if row["candidate_id"] is None:
        raise CapacityConflictError("FULL")
    return Selection(integer(row, "revision"), identifier(row, "candidate_id"))
