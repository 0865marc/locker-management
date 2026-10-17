"""Integrity of the versioned migration on official local workerd D1."""

import unittest
from datetime import datetime, timezone
from uuid import uuid4

from native_d1 import NativeD1

from adapters.database.d1 import D1DeliveryRepository, D1LockerRepository
from adapters.database.d1.bindings import D1BindingError
from adapters.database.d1.core import query, statement
from domain.deliveries import Delivery
from domain.lockers import Address, CompartmentBatch, Coordinates, Dimensions


class SchemaTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.database = await NativeD1().__aenter__()
        self.addAsyncCleanup(self.database.close)
        await self.database.migrate()

    async def test_eight_tables_and_reapply_keeps_data(self) -> None:
        lockers = D1LockerRepository(lambda: self.database)
        locker = await lockers.create(
            None,
            [CompartmentBatch(1, Dimensions(1, 2, 3))],
            address=Address("ES", "28001", "Madrid", "Madrid", "Calle", "1"),
            coordinates=Coordinates(40, -3),
        )
        await self.database.migrate()
        self.assertEqual(
            await D1LockerRepository(lambda: self.database).get_by_id(locker.id), locker
        )
        tables = await query(
            self.database,
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'",
        )
        names = {r["name"] for r in tables}
        self.assertTrue(
            {
                "deliveries",
                "returns",
                "lockers",
                "locker_compartments",
                "locker_assignments",
                "shipping_quotations",
                "shipping_provider_results",
                "shipping_offers",
            }.issubset(names)
        )

    async def test_invalid_direct_geography_dimensions_identity_and_dates(self) -> None:
        lockers = D1LockerRepository(lambda: self.database)
        locker = await lockers.create(
            "location", [CompartmentBatch(1, Dimensions(1, 2, 3))]
        )
        delivery = Delivery("t", "c", "name", datetime(2026, 1, 2, tzinfo=timezone.utc))
        await D1DeliveryRepository(lambda: self.database).save(delivery)
        invalid = [
            statement(
                self.database,
                "UPDATE lockers SET country_code='ES' WHERE id=?",
                str(locker.id),
            ),
            statement(
                self.database,
                "UPDATE lockers SET latitude=1 WHERE id=?",
                str(locker.id),
            ),
            statement(
                self.database,
                "UPDATE lockers SET latitude=91,longitude=0 WHERE id=?",
                str(locker.id),
            ),
            statement(
                self.database,
                "UPDATE lockers SET country_code='ES',postal_code='２８００１',province='p',city='c',street='s',street_number='1' WHERE id=?",
                str(locker.id),
            ),
            statement(
                self.database,
                "UPDATE lockers SET country_code='ES',postal_code='28001',province=?,city='c',street='s',street_number='1' WHERE id=?",
                "\u2003p",
                str(locker.id),
            ),
            statement(
                self.database, "UPDATE locker_compartments SET width_mm=2147483648"
            ),
            statement(self.database, "UPDATE locker_compartments SET width_mm=1.5"),
            statement(
                self.database, "UPDATE locker_compartments SET enabled=1,retired=1"
            ),
            statement(
                self.database,
                "INSERT INTO locker_compartments(id,locker_id,width_mm,height_mm,depth_mm,enabled,retired) VALUES (?,?,?,?,?,?,?)",
                str(uuid4()),
                str(uuid4()),
                1,
                1,
                1,
                1,
                0,
            ),
            statement(self.database, "UPDATE deliveries SET id=?", uuid4().hex),
            statement(
                self.database,
                "UPDATE deliveries SET received_at='2026-01-02T00:00:00Z'",
            ),
            statement(
                self.database,
                "UPDATE deliveries SET received_at='2026-02-30T00:00:00.000000Z'",
            ),
            statement(self.database, "UPDATE deliveries SET status='COLLECTED'"),
            statement(
                self.database,
                "UPDATE deliveries SET status='COLLECTED',collected_at='2025-01-01T00:00:00.000000Z'",
            ),
        ]
        for item in invalid:
            with self.assertRaises(D1BindingError):
                await item.run()
        self.assertEqual(await lockers.get_by_id(locker.id), locker)
        self.assertEqual(
            await D1DeliveryRepository(lambda: self.database).get_by_id(delivery.id),
            delivery,
        )

    async def test_assignment_xor_unique_and_historical_integrity(self) -> None:
        dims = Dimensions(1, 2, 3)
        locker = await D1LockerRepository(lambda: self.database).create(
            "location", [CompartmentBatch(1, dims)]
        )
        repo = D1DeliveryRepository(lambda: self.database)
        now = datetime(2026, 1, 2, tzinfo=timezone.utc)
        parcel = await repo.receive_in_locker(
            Delivery("t", "c", "r", now), locker.id, dims
        )
        other = Delivery("other", "c", "r", now)
        await repo.save(other)
        for sql, values in [
            ("UPDATE locker_assignments SET delivery_id=NULL", ()),
            ("UPDATE locker_assignments SET return_id=?", (str(uuid4()),)),
            (
                "UPDATE locker_assignments SET released_at='2025-01-01T00:00:00.000000Z'",
                (),
            ),
            (
                "INSERT INTO locker_assignments(id,compartment_id,delivery_id,width_mm,height_mm,depth_mm,assigned_at) VALUES (?,?,?,?,?,?,?)",
                (
                    str(uuid4()),
                    str(parcel.compartment_id),
                    str(other.id),
                    1,
                    2,
                    3,
                    "2026-01-02T00:00:00.000000Z",
                ),
            ),
        ]:
            with self.assertRaises(D1BindingError):
                await statement(self.database, sql, *values).run()
        self.assertTrue(await repo.save_exit(parcel.collect(now)))
        assert parcel.compartment_id is not None
        await D1LockerRepository(lambda: self.database).retire_compartment(
            locker.id, parcel.compartment_id
        )
        self.assertEqual(await repo.get_by_id(parcel.id), parcel.collect(now))
