from tests.integration.support import PostgresTestCase
from uuid import uuid4
D = {'width_mm': 10, 'height_mm': 20, 'depth_mm': 30}

class LockerHttpTests(PostgresTestCase):

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.client, _ = await self.actor()

    async def create(self, **changes):
        return await self.client.post('/lockers', json={'location_id': ' Site ', 'compartments': [{'quantity': 1, 'dimensions': D}]} | changes)

    async def availability(self, **changes):
        return await self.client.get('/lockers/availability', params={'location_id': 'Site'} | D | changes)

    async def test_configuration_endpoints_lifecycle_and_snapshot(self):
        self.assertEqual((await self.availability()).json()['reason'], 'NO_LOCKER')
        response = await self.create()
        self.assertEqual(response.status_code, 201, response.text)
        locker = response.json()
        self.assertEqual(locker['location_id'], 'Site')
        self.assertEqual(locker['compartment_count'], 1)
        identifier = locker['id']
        cell = locker['compartments'][0]
        self.assertEqual(set(cell), {'id', 'dimensions', 'enabled', 'occupied'})
        self.assertEqual((await self.client.get('/lockers', params={'location_id': ' Site '})).json(), [locker])
        self.assertEqual((await self.client.get(f'/lockers/{identifier}')).json(), locker)
        self.assertEqual((await self.availability()).json()['reason'], 'AVAILABLE')
        self.assertEqual((await self.availability(width_mm=100)).json()['reason'], 'NO_COMPATIBLE_CELL')
        changed = await self.client.patch(f"/lockers/{identifier}/compartments/{cell['id']}", json={'enabled': False})
        self.assertEqual(changed.status_code, 200, changed.text)
        self.assertEqual((await self.availability()).json()['reason'], 'NO_COMPATIBLE_CELL')
        added = await self.client.post(f'/lockers/{identifier}/compartments', json={'compartments': [{'quantity': 2, 'dimensions': D}]})
        self.assertEqual(added.status_code, 201, added.text)
        self.assertEqual(added.json()['compartment_count'], 3)
        self.assertEqual((await self.client.patch(f'/lockers/{identifier}', json={'active': False})).status_code, 200)
        self.assertEqual((await self.availability()).json()['reason'], 'LOCKER_INACTIVE')
        self.assertEqual((await self.client.delete(f"/lockers/{identifier}/compartments/{cell['id']}")).status_code, 204)
        self.assertEqual((await self.client.delete(f"/lockers/{identifier}/compartments/{cell['id']}")).status_code, 404)
        self.assertEqual((await self.client.get(f'/lockers/{identifier}')).json()['compartment_count'], 2)

    async def test_strict_validation_and_identity_errors(self):
        for location in (' ', 1, True, None):
            self.assertEqual((await self.create(location_id=location)).status_code, 422)
        for active in (1, 'true', None):
            self.assertEqual((await self.create(active=active)).status_code, 422)
        for invalid in (True, 1.0, '1', 0, -1, 2147483648):
            for key in D:
                self.assertEqual((await self.create(compartments=[{'quantity': 1, 'dimensions': D | {key: invalid}}])).status_code, 422)
        for quantity in (True, 1.0, '1', 0, -1, 1001):
            self.assertEqual((await self.create(compartments=[{'quantity': quantity, 'dimensions': D}])).status_code, 422)
        for compartments in ([], [{'quantity': 500, 'dimensions': D}, {'quantity': 501, 'dimensions': D}]):
            self.assertEqual((await self.create(compartments=compartments)).status_code, 422)
        self.assertEqual((await self.client.get('/lockers')).json(), [])
        self.assertEqual((await self.client.get('/lockers/not-uuid')).status_code, 422)
        self.assertEqual((await self.client.get(f'/lockers/{uuid4()}')).status_code, 404)
        locker = (await self.create()).json()
        identifier, cell = (locker['id'], locker['compartments'][0]['id'])
        for body in ({}, {'active': 1}, {'active': True, 'location_id': 'Elsewhere'}):
            self.assertEqual((await self.client.patch(f'/lockers/{identifier}', json=body)).status_code, 422)
        for body in ({}, {'enabled': 1}, {'dimensions': None}, {'enabled': None}, {'occupied': False}):
            self.assertEqual((await self.client.patch(f'/lockers/{identifier}/compartments/{cell}', json=body)).status_code, 422)
        for params in ({'width_mm': 0}, {'height_mm': 'bad'}, {'width_mm': '1.0'}, {'depth_mm': '1e1'}, {'depth_mm': 2147483648}, {'location_id': ' '}):
            self.assertEqual((await self.availability(**params)).status_code, 422)

    async def test_delivery_return_reception_exit_reuse_and_historical_fields(self):
        locker = (await self.create()).json()
        identifier, cell = (locker['id'], locker['compartments'][0]['id'])
        for flow, action in (('deliveries', 'collect'), ('deliveries', 'return-to-carrier'), ('returns', 'hand-over')):
            await self.client.patch(f'/lockers/{identifier}', json={'active': True})
            await self.client.patch(f'/lockers/{identifier}/compartments/{cell}', json={'dimensions': D})
            payload = {'tracking_number': 'T', 'carrier_code': 'C'}
            if flow == 'deliveries':
                payload['recipient_name'] = 'Ana'
            for invalid in ({'locker_id': identifier}, {'parcel_dimensions': D}, {'compartment_id': cell}):
                self.assertEqual((await self.client.post(f'/{flow}', json=payload | invalid)).status_code, 422)
            unknown = await self.client.post(f'/{flow}', json=payload | {'locker_id': str(uuid4()), 'parcel_dimensions': D})
            self.assertEqual(unknown.status_code, 404, unknown.text)
            received = await self.client.post(f'/{flow}', json=payload | {'locker_id': identifier, 'parcel_dimensions': D})
            self.assertEqual(received.status_code, 201, received.text)
            parcel = received.json()
            self.assertEqual(parcel['compartment_id'], cell)
            self.assertEqual(parcel['parcel_dimensions'], D)
            full = await self.client.post('/returns', json={'tracking_number': 'R', 'carrier_code': 'C', 'locker_id': identifier, 'parcel_dimensions': D})
            self.assertEqual(full.status_code, 409, full.text)
            self.assertEqual(full.json()['detail']['code'], 'FULL')
            self.assertEqual((await self.availability()).json()['reason'], 'FULL')
            for method, body in (('patch', {'enabled': False}), ('patch', {'dimensions': D}), ('delete', None)):
                result = await getattr(self.client, method)(f'/lockers/{identifier}/compartments/{cell}', **{'json': body} if body else {})
                self.assertEqual(result.status_code, 409, result.text)
            await self.client.patch(f'/lockers/{identifier}', json={'active': False})
            exited = await self.client.post(f"/{flow}/{parcel['id']}/{action}")
            self.assertEqual(exited.status_code, 200, exited.text)
            self.assertEqual(exited.json()['parcel_dimensions'], D)
            await self.client.patch(f'/lockers/{identifier}', json={'active': True})
            occupant = (await self.client.post('/returns', json={'tracking_number': 'B', 'carrier_code': 'C', 'locker_id': identifier, 'parcel_dimensions': D})).json()
            self.assertEqual((await self.client.post(f"/{flow}/{parcel['id']}/{action}")).status_code, 409)
            self.assertEqual((await self.availability()).json()['reason'], 'FULL')
            self.assertEqual((await self.client.post(f"/returns/{occupant['id']}/hand-over")).status_code, 200)
            await self.client.patch(f'/lockers/{identifier}/compartments/{cell}', json={'dimensions': {'width_mm': 1, 'height_mm': 1, 'depth_mm': 1}})
            self.assertIn(exited.json(), (await self.client.get(f'/{flow}')).json())
        self.assertEqual((await self.client.delete(f'/lockers/{identifier}/compartments/{cell}')).status_code, 204)
        for path in ('/deliveries', '/returns'):
            for record in (await self.client.get(path)).json():
                self.assertEqual(record['compartment_id'], cell)
                self.assertEqual(record['parcel_dimensions'], D)
