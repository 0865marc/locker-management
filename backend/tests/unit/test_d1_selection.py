"""Execute real selection SQL against SQLite and compare with domain selection.

This exercises exact integer ordering and the D1 row boundary, not WASM or CPU.
"""

import itertools
import random
import sqlite3
import unittest
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from uuid import UUID

from adapters.database.d1.bindings import D1PreparedStatement, D1Row, D1Value
from adapters.database.d1.lockers import Snapshot, choose_cell
from adapters.database.d1.selection import Selection, select
from domain.lockers import (
    CapacityConflictError,
    Compartment,
    Dimensions,
    Locker,
    LockerNotFoundError,
)

AT = "2026-10-18T00:00:00.000000Z"
MAXIMUM = 2147483647


class SQLiteStatement:
    def __init__(self, database: "SQLiteDatabase", sql: str) -> None:
        self.database = database
        self.sql = sql
        self.values: tuple[D1Value, ...] = ()

    def bind(self, *values: D1Value) -> "SQLiteStatement":
        self.values = values
        return self

    async def all(self) -> object:
        self.database.calls.append((self.sql, self.values))
        rows: list[sqlite3.Row] = self.database.connection.execute(
            self.sql, self.values
        ).fetchall()
        output: list[D1Row] = []
        for row in rows:
            item: D1Row = {}
            for name in row.keys():
                value: object = row[name]
                if not (value is None or isinstance(value, (str, int, float))):
                    raise AssertionError("Unexpected SQLite value")
                item[name] = value
            output.append(item)
        self.database.rows = output
        return {"success": True, "results": output, "meta": {"changes": 0}}

    async def first(self) -> object:
        raise AssertionError("Selection must use one compact query")

    async def run(self) -> object:
        raise AssertionError("Selection must not write")


class SQLiteDatabase:
    def __init__(self) -> None:
        self.connection = sqlite3.connect(":memory:")
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(
            (
                Path(__file__).resolve().parents[3]
                / "deploy/cloudflare/migrations/0001_initial.sql"
            ).read_text()
        )
        self.calls: list[tuple[str, tuple[D1Value, ...]]] = []
        self.rows: list[D1Row] = []

    def prepare(self, sql: str) -> SQLiteStatement:
        return SQLiteStatement(self, sql)

    async def batch(self, statements: Sequence[D1PreparedStatement]) -> object:
        raise AssertionError("Selection must not write")


class D1SelectionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.database = SQLiteDatabase()
        self.locker_id = UUID(int=9000)
        self.cells: list[Compartment] = []
        self.database.connection.execute(
            "INSERT INTO lockers(id,active,revision) VALUES (?,1,7)",
            (str(self.locker_id),),
        )
        self.assignment_count = 0

    def tearDown(self) -> None:
        self.database.connection.close()

    def cell(
        self,
        identifier: int,
        axes: tuple[int, int, int],
        *,
        enabled: bool = True,
        retired: bool = False,
    ) -> Compartment:
        cell = Compartment(
            self.locker_id,
            Dimensions(*axes),
            enabled=enabled,
            retired=retired,
            id=UUID(int=identifier),
        )
        self.database.connection.execute(
            "INSERT INTO locker_compartments(id,locker_id,width_mm,height_mm,depth_mm,enabled,retired) VALUES (?,?,?,?,?,?,?)",
            (str(cell.id), str(self.locker_id), *axes, int(enabled), int(retired)),
        )
        self.cells.append(cell)
        return cell

    def assign(self, cell: Compartment, flow: str, *, released: bool = False) -> None:
        self.assignment_count += 1
        parcel_id = str(UUID(int=100000 + self.assignment_count))
        if flow == "delivery":
            self.database.connection.execute(
                "INSERT INTO deliveries(id,tracking_number,carrier_code,recipient_name,received_at,status) VALUES (?,'t','c','n',?,'AWAITING_PICKUP')",
                (parcel_id, AT),
            )
        else:
            self.database.connection.execute(
                "INSERT INTO returns(id,tracking_number,carrier_code,received_at,status) VALUES (?,'t','c',?,'AWAITING_CARRIER')",
                (parcel_id, AT),
            )
        self.database.connection.execute(
            "INSERT INTO locker_assignments(id,compartment_id,delivery_id,return_id,width_mm,height_mm,depth_mm,assigned_at,released_at) VALUES (?,?,?,?,1,1,1,?,?)",
            (
                str(UUID(int=200000 + self.assignment_count)),
                str(cell.id),
                parcel_id if flow == "delivery" else None,
                parcel_id if flow == "return" else None,
                AT,
                AT if released else None,
            ),
        )
        if not released:
            self.cells = [
                replace(c, occupied=True) if c.id == cell.id else c for c in self.cells
            ]

    async def equivalent(
        self, dimensions: Dimensions, *, active: bool = True
    ) -> Selection | None:
        # snapshot omits retired cells; choose_cell then uses domain.select_compartment.
        locker = Locker(
            id=self.locker_id,
            active=active,
            compartments=tuple(c for c in self.cells if not c.retired),
        )
        before = len(self.database.calls)
        try:
            expected = choose_cell(Snapshot(locker, 7), dimensions)
        except CapacityConflictError as expected_error:
            with self.assertRaises(CapacityConflictError) as actual:
                await select(self.database, self.locker_id, dimensions)
            self.assertEqual(actual.exception.code, expected_error.code)
            result = None
        else:
            result = await select(self.database, self.locker_id, dimensions)
            self.assertEqual(result, Selection(7, expected.id))
        self.assertEqual(len(self.database.calls) - before, 1)
        self.assertEqual(len(self.database.rows), 1)
        self.assertEqual(
            set(self.database.rows[0]),
            {"id", "active", "revision", "has_compatible", "candidate_id"},
        )
        return result

    async def test_all_axis_permutations_match_domain(self) -> None:
        for cell_axes in itertools.permutations((3, 5, 7)):
            self.database.connection.execute("DELETE FROM locker_compartments")
            self.cells.clear()
            self.cell(1, (3, 4, 8))  # Smaller volume, but middle axis cannot fit.
            self.cell(20, (cell_axes[0], cell_axes[1], cell_axes[2]))
            for parcel_axes in itertools.permutations((3, 5, 7)):
                await self.equivalent(Dimensions(*parcel_axes))

    async def test_exact_volumes_beyond_64_bits_and_float_precision(self) -> None:
        for n in (1_000_000_000, MAXIMUM - 1):
            self.database.connection.execute("DELETE FROM locker_compartments")
            self.cells.clear()
            larger = self.cell(1, (n, n, n))
            smaller = self.cell(2, (n - 1, n, n + 1))
            self.assertGreater(larger.dimensions.volume, 2**64)
            self.assertEqual(
                float(larger.dimensions.volume), float(smaller.dimensions.volume)
            )
            result = await self.equivalent(Dimensions(1, 1, 1))
            self.assertEqual(result, Selection(7, smaller.id))
        self.cell(3, (MAXIMUM, MAXIMUM, MAXIMUM))
        result = await self.equivalent(Dimensions(MAXIMUM, MAXIMUM, MAXIMUM))
        self.assertEqual(result, Selection(7, UUID(int=3)))

    async def test_equal_volume_uuid_binary_tie_is_independent_of_axis_order(
        self,
    ) -> None:
        self.cell(0x100, (2, 3, 4))
        self.cell(0x0F, (4, 2, 3))
        self.cell(0x01, (1, 6, 4))  # Same volume, incompatible with (2,3,4).
        result = await self.equivalent(Dimensions(2, 3, 4))
        self.assertEqual(result, Selection(7, UUID(int=0x0F)))

    async def test_both_active_assignment_types_and_released_history(self) -> None:
        first = self.cell(1, (10, 10, 10))
        second = self.cell(2, (10, 10, 10))
        third = self.cell(3, (10, 10, 10))
        self.assign(first, "delivery")
        self.assign(second, "return")
        self.assign(third, "delivery", released=True)
        self.assign(third, "return", released=True)
        self.assertEqual(
            await self.equivalent(Dimensions(1, 1, 1)), Selection(7, third.id)
        )
        self.assign(third, "return")
        await self.equivalent(
            Dimensions(1, 1, 1)
        )  # Compatible but all occupied => FULL.
        self.assertEqual(self.database.rows[0]["has_compatible"], 1)
        self.assertIsNone(self.database.rows[0]["candidate_id"])

    async def test_decision_error_precedence_and_disabled_retired_cells(self) -> None:
        with self.assertRaises(LockerNotFoundError):
            await select(self.database, UUID(int=9999), Dimensions(1, 1, 1))
        self.assertEqual(self.database.rows, [])
        self.cell(1, (MAXIMUM, MAXIMUM, MAXIMUM), enabled=False)
        self.cell(2, (MAXIMUM, MAXIMUM, MAXIMUM), enabled=False, retired=True)
        await self.equivalent(Dimensions(1, 1, 1))
        self.assertEqual(self.database.rows[0]["has_compatible"], 0)
        self.database.connection.execute("UPDATE lockers SET active=0")
        await self.equivalent(Dimensions(1, 1, 1), active=False)
        enabled = self.cell(3, (1, 1, 1))
        self.assign(enabled, "delivery")
        await self.equivalent(Dimensions(1, 1, 1), active=False)
        self.database.connection.execute("UPDATE lockers SET active=1")
        await self.equivalent(Dimensions(1, 1, 1))

    async def test_candidates_and_compatibility_are_scoped_to_requested_locker(
        self,
    ) -> None:
        other = UUID(int=9001)
        self.database.connection.execute(
            "INSERT INTO lockers(id,active) VALUES (?,1)", (str(other),)
        )
        self.database.connection.execute(
            "INSERT INTO locker_compartments(id,locker_id,width_mm,height_mm,depth_mm,enabled) VALUES (?,?,1,1,1,1)",
            (str(UUID(int=1)), str(other)),
        )
        selected = self.cell(2, (2, 2, 2))
        self.assertEqual(
            await self.equivalent(Dimensions(1, 1, 1)), Selection(7, selected.id)
        )
        self.database.connection.execute(
            "UPDATE locker_compartments SET enabled=0 WHERE locker_id=?",
            (str(self.locker_id),),
        )
        self.cells = [replace(cell, enabled=False) for cell in self.cells]
        await self.equivalent(Dimensions(1, 1, 1))

    async def test_deterministic_varied_configurations_match_domain(self) -> None:
        randomizer = random.Random(20261018)
        for case in range(60):
            self.database.connection.execute("DELETE FROM locker_assignments")
            self.database.connection.execute("DELETE FROM locker_compartments")
            self.cells.clear()
            values = (
                tuple(range(1, 41))
                if case < 30
                else (1, 65536, 10**9, MAXIMUM - 2, MAXIMUM - 1, MAXIMUM)
            )
            for index in range(16):
                axes = tuple(randomizer.choice(values) for _ in range(3))
                retired = randomizer.randrange(8) == 0
                cell = self.cell(
                    index + 1,
                    (axes[0], axes[1], axes[2]),
                    enabled=not retired and randomizer.randrange(5) != 0,
                    retired=retired,
                )
                if not retired and randomizer.randrange(3) == 0:
                    self.assign(cell, "delivery" if index % 2 else "return")
            parcel = Dimensions(*(randomizer.choice(values) for _ in range(3)))
            with self.subTest(case=case):
                await self.equivalent(parcel)
