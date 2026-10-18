"""Stored custody assignments remain trackable after their cell is released."""

from uuid import uuid4

from tests.integration.support import PostgresTestCase


class TrackingHttpIntegrationTests(PostgresTestCase):
    async def test_receive_exit_and_track_public_assignment_across_both_flows(
        self,
    ) -> None:
        _, client, _ = await self.application()
        response = await client.post(
            "/lockers",
            json={
                "location_id": "Tracking integration",
                "coordinates": {"latitude": 40.4, "longitude": -3.7},
                "compartments": [
                    {
                        "quantity": 1,
                        "dimensions": {
                            "width_mm": 400,
                            "height_mm": 400,
                            "depth_mm": 600,
                        },
                    }
                ],
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        locker_id = response.json()["id"]
        for path, payload, action, pending, terminal in (
            (
                "/deliveries",
                {
                    "tracking_number": "PRIVATE-D",
                    "carrier_code": "PRIVATE-C",
                    "recipient_name": "PRIVATE-N",
                    "recipient_phone": "PRIVATE-P",
                },
                "collect",
                "AWAITING_PICKUP",
                "COLLECTED",
            ),
            (
                "/returns",
                {
                    "tracking_number": "PRIVATE-R",
                    "carrier_code": "PRIVATE-C",
                    "sender_name": "PRIVATE-N",
                },
                "hand-over",
                "AWAITING_CARRIER",
                "HANDED_OVER",
            ),
        ):
            with self.subTest(path=path):
                created = await client.post(
                    path,
                    json={
                        **payload,
                        "locker_id": locker_id,
                        "parcel_dimensions": {
                            "width_mm": 100,
                            "height_mm": 100,
                            "depth_mm": 100,
                        },
                    },
                )
                self.assertEqual(created.status_code, 201, created.text)
                identifier = created.json()["id"]
                inactive = await client.patch(
                    f"/lockers/{locker_id}", json={"active": False}
                )
                self.assertEqual(inactive.status_code, 200)
                current = await client.get(f"/tracking/{identifier}")
                self.assertEqual(current.status_code, 200, current.text)
                self.assertEqual(current.json()["status"], pending)
                self.assertEqual(current.json()["locker_relation"], "current")
                self.assertEqual(current.json()["locker_id"], locker_id)
                self.assertEqual(
                    set(current.json()),
                    {"id", "kind", "status", "locker_relation", "locker_id", "locker"},
                )
                self.assertEqual(
                    set(current.json()["locker"]),
                    {"location_id", "address", "coordinates"},
                )
                self.assertNotIn("PRIVATE-", current.text)
                exited = await client.post(f"{path}/{identifier}/{action}")
                self.assertEqual(exited.status_code, 200, exited.text)
                last = await client.get(f"/tracking/{identifier}")
                self.assertEqual(last.status_code, 200)
                self.assertEqual(last.json()["status"], terminal)
                self.assertEqual(last.json()["locker_relation"], "last_known")
                self.assertEqual(last.json()["locker"], current.json()["locker"])
                self.assertEqual(
                    (await client.get(f"{path}")).json()[0]["id"], identifier
                )
                await client.patch(f"/lockers/{locker_id}", json={"active": True})

        unassigned = await client.post(
            "/returns", json={"tracking_number": "UNASSIGNED", "carrier_code": "C"}
        )
        self.assertEqual(unassigned.status_code, 201)
        result = await client.get(f"/tracking/{unassigned.json()['id']}")
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["locker_relation"], "unassigned")
        self.assertIsNone(result.json()["locker_id"])
        self.assertIsNone(result.json()["locker"])
        self.assertEqual((await client.get(f"/tracking/{uuid4()}")).status_code, 404)
        self.assertEqual((await client.get("/tracking/not-a-uuid")).status_code, 422)
