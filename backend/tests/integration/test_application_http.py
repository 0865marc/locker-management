"""Full applications share committed data only within this case's schema."""
from uuid import uuid4
from tests.integration.support import PostgresTestCase


class ApplicationHttpTests(PostgresTestCase):
    async def test_create_exit_list_and_persist_across_app_instances(self):
        created = {}
        cases = (
            ('/deliveries', {'tracking_number': f'PKG-{uuid4()}', 'carrier_code': 'carrier-a',
                            'recipient_name': 'Ana García', 'recipient_phone': ' 600123456 ',
                            'pickup_deadline_at': '2020-01-01T12:00:00+02:00'}, 'collect', 'COLLECTED'),
            ('/deliveries', {'tracking_number': f'PKG-{uuid4()}', 'carrier_code': 'carrier-a',
                            'recipient_name': 'Luis Pérez'}, 'return-to-carrier', 'RETURNED_TO_CARRIER'),
            ('/returns', {'tracking_number': f'RET-{uuid4()}', 'carrier_code': 'carrier-a',
                         'sender_name': ' '}, 'hand-over', 'HANDED_OVER'),
        )
        app, client, engine = await self.application()
        for path, payload, action, status in cases:
            with self.subTest(path=path, action=action):
                response = await client.post(path, json=payload | {'tracking_number': f'  {payload["tracking_number"]}  '})
                self.assertEqual(response.status_code, 201, response.text)
                item = response.json()
                self.assertEqual(item['tracking_number'], payload['tracking_number'])
                self.assertTrue(item['received_at'].endswith(('Z', '+00:00')))
                self.assertIsNone(item['locker_id'])
                self.assertIsNone(item['compartment_id'])
                self.assertIsNone(item['parcel_dimensions'])
                if action == 'collect':
                    self.assertEqual(item['recipient_phone'], '600123456')
                    self.assertEqual(item['pickup_deadline_at'], '2020-01-01T10:00:00Z')
                if path == '/returns':
                    self.assertIsNone(item['sender_name'])
                action_path = f'{path}/{item["id"]}/{action}'
                exited = await client.post(action_path, json={})
                self.assertEqual(exited.status_code, 200, exited.text)
                self.assertEqual(exited.json()['status'], status)
                created.setdefault(path, []).append(exited.json())
                self.assertEqual((await client.post(action_path)).status_code, 409)
                if action == 'collect':
                    self.assertEqual((await client.post(f'{path}/{item["id"]}/return-to-carrier')).status_code, 409)
                for invalid in ({}, payload | {'tracking_number': '   '}, payload | {'tracking_number': 123}):
                    self.assertEqual((await client.post(path, json=invalid)).status_code, 422)
        # Close the first application and its pool before opening the next instance.
        await self.close_application(client)
        second, _ = await self.actor()
        for path, items in created.items():
            response = await second.get(path)
            self.assertEqual(response.status_code, 200)
            for item in items:
                self.assertIn(item, response.json())
        for path in (f'/deliveries/{uuid4()}/collect', f'/returns/{uuid4()}/hand-over'):
            self.assertEqual((await second.post(path)).status_code, 404)


class UnpreparedApplicationTests(PostgresTestCase):
    initial_revision = None

    async def test_startup_and_openapi_leave_unprepared_schema_empty(self):
        self.assertEqual(await self.snapshot(), ({}, {}))
        _, client, _ = await self.application()
        self.assertEqual((await client.get('/openapi.json')).status_code, 200)
        self.assertEqual(await self.snapshot(), ({}, {}))
