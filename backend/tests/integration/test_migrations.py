"""Preserved Alembic history scenarios against isolated PostgreSQL schemas."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import text

from tests.integration.support import PostgresTestCase

NOW = datetime(2026, 10, 14, 12, 30, 25, 123456, tzinfo=timezone.utc)


class MigrationTests(PostgresTestCase):
    initial_revision = None

    async def test_initial_revision_retains_legacy_columns(self):
        await self.migrate("upgrade", "0001")
        definitions, rows = await self.snapshot()
        self.assertEqual(
            [column["name"] for column in definitions["deliveries"][0]],
            ["id", "address"],
        )
        self.assertEqual(
            [column["name"] for column in definitions["returns"][0]], ["id", "reason"]
        )
        self.assertEqual(rows["alembic_version"], [("0001",)])

    async def test_empty_round_trip_and_current_schema_match_models(self):
        await self.migrate("upgrade", "head")
        await self.migrate("check")
        current = await self.snapshot()
        self.assertEqual(current[1]["alembic_version"], [("0005",)])
        await self.migrate("downgrade", "0001")
        self.assertEqual((await self.snapshot())[1]["alembic_version"], [("0001",)])
        await self.migrate("upgrade", "head")
        await self.migrate("check")
        self.assertEqual(await self.snapshot(), current)
        await self.migrate("downgrade", "base")
        definitions, _ = await self.snapshot()
        self.assertFalse(
            {
                "deliveries",
                "returns",
                "lockers",
                "locker_compartments",
                "locker_assignments",
            }
            & definitions.keys()
        )
        await self.migrate("upgrade", "head")
        await self.migrate("check")
        self.assertEqual(await self.snapshot(), current)

    async def test_populated_legacy_tables_block_upgrade_before_any_change(self):
        await self.migrate("upgrade", "0001")
        for tables in (("deliveries",), ("returns",), ("deliveries", "returns")):
            with self.subTest(tables=tables):
                async with self.engine.begin() as connection:
                    for table in tables:
                        field = "address" if table == "deliveries" else "reason"
                        await connection.execute(
                            text(
                                f"INSERT INTO {table} (id, {field}) VALUES (:id, :value)"
                            ),
                            {"id": uuid4(), "value": "Preserve this real value"},
                        )
                before = await self.snapshot()
                with self.assertRaisesRegex(
                    RuntimeError, "explicit data migration"
                ) as error:
                    await self.migrate("upgrade", "head")
                for table in tables:
                    self.assertIn(table, str(error.exception))
                self.assertIn("lack required", str(error.exception))
                self.assertEqual(await self.snapshot(), before)
                async with self.engine.begin() as connection:
                    for table in tables:
                        await connection.execute(text(f"DELETE FROM {table}"))

    async def test_populated_parcel_tables_block_downgrade_before_any_change(self):
        await self.migrate("upgrade", "0002")
        for tables in (("deliveries",), ("returns",), ("deliveries", "returns")):
            with self.subTest(tables=tables):
                async with self.engine.begin() as connection:
                    for table in tables:
                        columns = (
                            "id, tracking_number, carrier_code, received_at, status"
                        )
                        values = ":id, :tracking, :carrier, :received, :status"
                        if table == "deliveries":
                            columns += ", recipient_name"
                            values += ", :recipient"
                        await connection.execute(
                            text(f"INSERT INTO {table} ({columns}) VALUES ({values})"),
                            {
                                "id": uuid4(),
                                "tracking": "PKG-42",
                                "carrier": "carrier-a",
                                "received": NOW,
                                "recipient": "Ana",
                                "status": "AWAITING_PICKUP"
                                if table == "deliveries"
                                else "AWAITING_CARRIER",
                            },
                        )
                before = await self.snapshot()
                with self.assertRaisesRegex(
                    RuntimeError, "would lose parcel custody data"
                ):
                    await self.migrate("downgrade", "0001")
                self.assertEqual(await self.snapshot(), before)
                async with self.engine.begin() as connection:
                    for table in tables:
                        await connection.execute(text(f"DELETE FROM {table}"))

    async def populate_current_parcels(self):
        """Typed SQL preserves every existing pending and terminal custody field."""
        self.delivery_ids = [uuid4() for _ in range(3)]
        async with self.engine.begin() as connection:
            for index, status in enumerate(
                ("AWAITING_PICKUP", "COLLECTED", "RETURNED_TO_CARRIER")
            ):
                await connection.execute(
                    text(
                        "INSERT INTO deliveries "
                        "(id, tracking_number, carrier_code, recipient_name, recipient_phone, received_at, "
                        "pickup_deadline_at, status, collected_at, returned_to_carrier_at) "
                        "VALUES (:id, :tracking, :carrier, :recipient, :phone, :received, :deadline, :status, :collected, :returned)"
                    ),
                    {
                        "id": self.delivery_ids[index],
                        "tracking": f"D-{index}",
                        "carrier": "carrier-a",
                        "recipient": "Ana",
                        "phone": "600123456",
                        "received": NOW,
                        "deadline": NOW + timedelta(days=6),
                        "status": status,
                        "collected": NOW + timedelta(days=1)
                        if status == "COLLECTED"
                        else None,
                        "returned": NOW + timedelta(days=1)
                        if status == "RETURNED_TO_CARRIER"
                        else None,
                    },
                )
            for index, status in enumerate(("AWAITING_CARRIER", "HANDED_OVER")):
                await connection.execute(
                    text(
                        "INSERT INTO returns (id, tracking_number, carrier_code, sender_name, received_at, status, handed_over_at) "
                        "VALUES (:id, :tracking, :carrier, :sender, :received, :status, :handed)"
                    ),
                    {
                        "id": uuid4(),
                        "tracking": f"R-{index}",
                        "carrier": "carrier-b",
                        "sender": "Luis",
                        "received": NOW,
                        "status": status,
                        "handed": NOW + timedelta(days=1)
                        if status == "HANDED_OVER"
                        else None,
                    },
                )

    async def test_populated_0002_upgrade_is_additive_and_empty_locker_downgrade_preserves_parcels(
        self,
    ):
        await self.migrate("upgrade", "0002")
        await self.populate_current_parcels()
        original = await self.snapshot()
        await self.migrate("upgrade", "0003")
        current = await self.snapshot()
        self.assertEqual(current[1]["alembic_version"], [("0003",)])
        for table in ("deliveries", "returns"):
            self.assertEqual(current[0][table], original[0][table])
            self.assertEqual(current[1][table], original[1][table])
        for table in ("lockers", "locker_compartments", "locker_assignments"):
            self.assertEqual(current[1][table], [])
        await self.migrate("downgrade", "0002")
        self.assertEqual(await self.snapshot(), original)
        await self.migrate("upgrade", "0003")
        self.assertEqual(await self.snapshot(), current)

        await self.migrate("upgrade", "head")
        await self.migrate("check")

    async def test_locker_downgrade_preserves_configuration_and_released_retired_history(
        self,
    ):
        await self.migrate("upgrade", "head")
        await self.populate_current_parcels()
        for state in ("locker", "cell", "active", "historical"):
            with self.subTest(state=state):
                locker_id, cell_id = uuid4(), uuid4()
                async with self.engine.begin() as connection:
                    await connection.execute(
                        text(
                            "INSERT INTO lockers (id, location_id, active) VALUES (:id, :location, :active)"
                        ),
                        {"id": locker_id, "location": "MAD-01", "active": True},
                    )
                    if state != "locker":
                        await connection.execute(
                            text(
                                "INSERT INTO locker_compartments (id, locker_id, width_mm, height_mm, depth_mm, enabled, retired) "
                                "VALUES (:id, :locker, :width, :height, :depth, :enabled, :retired)"
                            ),
                            {
                                "id": cell_id,
                                "locker": locker_id,
                                "width": 100,
                                "height": 200,
                                "depth": 300,
                                "enabled": state != "historical",
                                "retired": state == "historical",
                            },
                        )
                    if state in ("active", "historical"):
                        await connection.execute(
                            text(
                                "INSERT INTO locker_assignments "
                                "(id, compartment_id, delivery_id, width_mm, height_mm, depth_mm, assigned_at, released_at) "
                                "VALUES (:id, :cell, :delivery, :width, :height, :depth, :assigned, :released)"
                            ),
                            {
                                "id": uuid4(),
                                "cell": cell_id,
                                "delivery": self.delivery_ids[
                                    0 if state == "active" else 1
                                ],
                                "width": 10,
                                "height": 20,
                                "depth": 30,
                                "assigned": NOW,
                                "released": NOW + timedelta(days=1)
                                if state == "historical"
                                else None,
                            },
                        )
                before = await self.snapshot()
                with self.assertRaisesRegex(RuntimeError, "(?i)(locker|custody|data)"):
                    await self.migrate("downgrade", "0002")
                self.assertEqual(await self.snapshot(), before)
                async with self.engine.begin() as connection:
                    # Clear only this subcase's rows in its generated private schema.
                    await connection.execute(
                        text(
                            "DELETE FROM locker_assignments WHERE compartment_id=:cell"
                        ),
                        {"cell": cell_id},
                    )
                    await connection.execute(
                        text("DELETE FROM locker_compartments WHERE id=:cell"),
                        {"cell": cell_id},
                    )
                    await connection.execute(
                        text("DELETE FROM lockers WHERE id=:locker"),
                        {"locker": locker_id},
                    )

    async def test_populated_0003_geography_upgrade_and_safe_round_trip(self) -> None:
        await self.migrate("upgrade", "0003")
        await self.populate_current_parcels()
        locker_ids = [uuid4(), uuid4()]
        cell_ids = [uuid4(), uuid4()]
        async with self.engine.begin() as connection:
            for index in range(2):
                await connection.execute(
                    text(
                        "INSERT INTO lockers(id,location_id,active) VALUES(:id,:location,:active)"
                    ),
                    {
                        "id": locker_ids[index],
                        "location": f"Site-{index}",
                        "active": index == 0,
                    },
                )
                await connection.execute(
                    text(
                        "INSERT INTO locker_compartments(id,locker_id,width_mm,height_mm,depth_mm,enabled,retired) VALUES(:id,:locker,10,20,30,:enabled,:retired)"
                    ),
                    {
                        "id": cell_ids[index],
                        "locker": locker_ids[index],
                        "enabled": index == 0,
                        "retired": index == 1,
                    },
                )
                await connection.execute(
                    text(
                        "INSERT INTO locker_assignments(id,compartment_id,delivery_id,width_mm,height_mm,depth_mm,assigned_at,released_at) VALUES(:id,:cell,:parcel,1,2,3,:assigned,:released)"
                    ),
                    {
                        "id": uuid4(),
                        "cell": cell_ids[index],
                        "parcel": self.delivery_ids[index],
                        "assigned": NOW,
                        "released": NOW + timedelta(seconds=1) if index else None,
                    },
                )
        original = await self.snapshot()
        await self.migrate("upgrade", "0004")
        current = await self.snapshot()
        self.assertEqual(current[1]["alembic_version"], [("0004",)])
        for table in (
            "deliveries",
            "returns",
            "locker_compartments",
            "locker_assignments",
        ):
            self.assertEqual(current[0][table], original[0][table])
            self.assertEqual(current[1][table], original[1][table])
        self.assertEqual(
            [tuple(row[:3]) for row in current[1]["lockers"]],
            [tuple(row) for row in original[1]["lockers"]],
        )
        self.assertTrue(
            all(
                all(value is None for value in row[3:]) for row in current[1]["lockers"]
            )
        )
        columns = {column["name"]: column for column in current[0]["lockers"][0]}
        self.assertTrue(columns["location_id"]["nullable"])
        self.assertEqual(
            set(current[0]),
            {
                "alembic_version",
                "deliveries",
                "returns",
                "lockers",
                "locker_compartments",
                "locker_assignments",
            },
        )
        await self.migrate("downgrade", "0003")
        self.assertEqual(await self.snapshot(), original)
        await self.migrate("upgrade", "0004")
        self.assertEqual(await self.snapshot(), current)

    async def test_geography_and_null_alias_block_downgrade_before_ddl(self) -> None:
        await self.migrate("upgrade", "head")
        identifier = uuid4()
        async with self.engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO lockers(id,location_id,active) VALUES(:id,:location,true)"
                ),
                {"id": identifier, "location": "Legacy"},
            )
        cases = [
            "country_code='ES',postal_code='01001',province='P',city='C',street='S',street_number='12B'",
            "latitude=0,longitude=0",
            "location_id=NULL",
        ]
        for values in cases:
            async with self.engine.begin() as connection:
                await connection.execute(
                    text(f"UPDATE lockers SET {values} WHERE id=:id"),
                    {"id": identifier},
                )
            before = await self.snapshot()
            with self.assertRaisesRegex(RuntimeError, "preserve"):
                await self.migrate("downgrade", "0003")
            self.assertEqual(await self.snapshot(), before)
            async with self.engine.begin() as connection:
                await connection.execute(
                    text(
                        "UPDATE lockers SET location_id='Legacy',country_code=NULL,postal_code=NULL,province=NULL,city=NULL,street=NULL,street_number=NULL,latitude=NULL,longitude=NULL WHERE id=:id"
                    ),
                    {"id": identifier},
                )

    async def test_geographic_database_checks_reject_partial_invalid_and_nonfinite_values(
        self,
    ) -> None:
        from sqlalchemy.exc import IntegrityError

        await self.migrate("upgrade", "head")
        identifier = uuid4()
        async with self.engine.begin() as connection:
            await connection.execute(
                text(
                    "INSERT INTO lockers(id,location_id,active) VALUES(:id,'Legacy',true)"
                ),
                {"id": identifier},
            )
        before = await self.snapshot()
        address = "country_code='ES',postal_code='01001',province='P',city='C',street='S',street_number='12B'"
        invalid = [
            "country_code='ES'",
            "postal_code='01001'",
            "province='P'",
            "city='C'",
            "street='S'",
            "street_number='N'",
            address.replace("country_code='ES'", "country_code='FR'"),
            address.replace("postal_code='01001'", "postal_code='０１００１'"),
            address.replace("postal_code='01001'", "postal_code='1001'"),
            address.replace("province='P'", "province=''"),
            address.replace("city='C'", "city=' C'"),
            address.replace("street='S'", "street=E'\\t'"),
            address.replace("street_number='12B'", "street_number=NULL"),
            "latitude=0",
            "longitude=0",
            "latitude=91,longitude=0",
            "latitude=0,longitude=-181",
            "latitude='NaN'::double precision,longitude=0",
            "latitude=0,longitude='NaN'::double precision",
            "latitude='Infinity'::double precision,longitude=0",
            "latitude=0,longitude='-Infinity'::double precision",
        ]
        for whitespace in ("\u00a0", "\x1c"):
            for text_value in (
                whitespace,
                whitespace + "P",
                "P" + whitespace,
                whitespace + "P" + whitespace,
            ):
                async with self.engine.begin() as connection:
                    # This legal full value isolates the text constraint on each update.
                    await connection.execute(
                        text(f"UPDATE lockers SET {address} WHERE id=:id"),
                        {"id": identifier},
                    )
                valid = await self.snapshot()
                with (
                    self.subTest(text_value=repr(text_value)),
                    self.assertRaises(IntegrityError),
                ):
                    async with self.engine.begin() as connection:
                        await connection.execute(
                            text("UPDATE lockers SET province=:value WHERE id=:id"),
                            {"value": text_value, "id": identifier},
                        )
                self.assertEqual(await self.snapshot(), valid)
                async with self.engine.begin() as connection:
                    await connection.execute(
                        text(
                            "UPDATE lockers SET country_code=NULL,postal_code=NULL,province=NULL,city=NULL,street=NULL,street_number=NULL WHERE id=:id"
                        ),
                        {"id": identifier},
                    )
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(IntegrityError):
                async with self.engine.begin() as connection:
                    await connection.execute(
                        text(f"UPDATE lockers SET {values} WHERE id=:id"),
                        {"id": identifier},
                    )
            self.assertEqual(await self.snapshot(), before)
        async with self.engine.begin() as connection:
            await connection.execute(
                text(
                    f"UPDATE lockers SET {address},latitude=-90,longitude=180 WHERE id=:id"
                ),
                {"id": identifier},
            )
        await self.migrate("check")

    async def test_populated_0004_quotation_upgrade_and_empty_storage_round_trip(self):
        await self.migrate("upgrade", "0004")
        await self.populate_current_parcels()
        async with self.engine.begin() as connection:
            for index in range(2):
                locker_id, cell_id = uuid4(), uuid4()
                await connection.execute(
                    text(
                        "INSERT INTO lockers(id,location_id,active,country_code,postal_code,province,city,street,street_number,latitude,longitude) VALUES(:id,NULL,:active,'ES','01001','Province','City','Street','1',40,-3)"
                    ),
                    {"id": locker_id, "active": index == 0},
                )
                await connection.execute(
                    text(
                        "INSERT INTO locker_compartments(id,locker_id,width_mm,height_mm,depth_mm,enabled,retired) VALUES(:id,:locker,10,20,30,:enabled,:retired)"
                    ),
                    {
                        "id": cell_id,
                        "locker": locker_id,
                        "enabled": index == 0,
                        "retired": index == 1,
                    },
                )
                await connection.execute(
                    text(
                        "INSERT INTO locker_assignments(id,compartment_id,delivery_id,width_mm,height_mm,depth_mm,assigned_at,released_at) VALUES(:id,:cell,:parcel,1,2,3,:assigned,:released)"
                    ),
                    {
                        "id": uuid4(),
                        "cell": cell_id,
                        "parcel": self.delivery_ids[index],
                        "assigned": NOW,
                        "released": NOW + timedelta(seconds=1) if index else None,
                    },
                )
        original = await self.snapshot()
        await self.migrate("upgrade", "0005")
        await self.migrate("check")
        current = await self.snapshot()
        self.assertEqual(current[1]["alembic_version"], [("0005",)])
        for table in original[0]:
            if table != "alembic_version":
                self.assertEqual(current[0][table], original[0][table])
                self.assertEqual(current[1][table], original[1][table])
        for table in (
            "shipping_quotations",
            "shipping_provider_results",
            "shipping_offers",
        ):
            self.assertEqual(current[1][table], [])
        await self.migrate("downgrade", "0004")
        self.assertEqual(await self.snapshot(), original)
        await self.migrate("upgrade", "0005")
        self.assertEqual(await self.snapshot(), current)
