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

    async def test_geography_create_patch_validation_and_nullable_representation(self) -> None:
        address = {'country_code': 'ES', 'postal_code': '01001', 'province': ' Araba ', 'city': ' Vitoria ', 'street': ' Calle ', 'street_number': ' 12B '}
        payload = {'compartments': [{'quantity': 1, 'dimensions': D}], 'address': address, 'coordinates': {'latitude': -90, 'longitude': 180}}
        result = await self.client.post('/lockers', json=payload)
        self.assertEqual(result.status_code, 201, result.text)
        locker = result.json()
        self.assertIsNone(locker['location_id'])
        self.assertEqual(locker['address'], address | {'province': 'Araba', 'city': 'Vitoria', 'street': 'Calle', 'street_number': '12B'})
        path = f'/lockers/{locker["id"]}'
        self.assertEqual((await self.client.get(path)).json(), locker)
        self.assertIn(locker, (await self.client.get('/lockers')).json())
        self.assertEqual((await self.client.get('/lockers', params={'location_id': '01001'})).json(), [])
        self.assertEqual((await self.availability(location_id='01001')).json()['reason'], 'NO_LOCKER')
        active_only = await self.client.patch(path, json={'active': False})
        self.assertEqual(active_only.json(), locker | {'active': False})
        replacement = address | {'street': 'Otra', 'street_number': 's/n'}
        replaced = await self.client.patch(path, json={'address': replacement, 'coordinates': {'latitude': 90, 'longitude': -180}})
        self.assertEqual(replaced.status_code, 200, replaced.text)
        self.assertFalse(replaced.json()['active'])
        self.assertEqual(replaced.json()['address']['street_number'], 's/n')
        preserved = replaced.json()
        bad_addresses = [address | {'country_code': 'FR'}, address | {'postal_code': 1001}, address | {'postal_code': '０１００１'}, address | {'postal_code': '0101'}, address | {'province': '\t'}, address | {'street_number': None}, address | {'extra': 'x'}, {key: value for key, value in address.items() if key != 'city'}]
        bad_coordinates = [{'latitude': 1}, {'latitude': '1', 'longitude': 2}, {'latitude': True, 'longitude': 2}, {'latitude': 91, 'longitude': 2}, {'latitude': 10**400, 'longitude': 2}, {'latitude': 1, 'longitude': -181}, {'latitude': 1, 'longitude': 2, 'extra': 0}]
        for invalid in [*({'address': value} for value in bad_addresses), *({'coordinates': value} for value in bad_coordinates), {}, {'active': None}, {'location_id': 'other'}]:
            result = await self.client.patch(path, json={'active': True} | invalid if invalid else {})
            self.assertEqual(result.status_code, 422, result.text)
            self.assertEqual((await self.client.get(path)).json(), preserved)
        # Non-standard JSON numeric tokens must fail validation, too.
        for token in ('NaN', 'Infinity', '-Infinity'):
            result = await self.client.patch(path, content='{"coordinates":{"latitude":' + token + ',"longitude":0}}', headers={'Content-Type': 'application/json'})
            self.assertEqual(result.status_code, 422, result.text)
        for malformed in ('{"coordinates":[NaN]}',
                          '{"coordinates":{"latitude":[NaN],"longitude":0}}',
                          '{"coordinates":{"latitude":0,"longitude":0,"extra":NaN}}',
                          '{"address":{"country_code":NaN}}'):
            for endpoint, method in (('/lockers', self.client.post), (path, self.client.patch)):
                result = await method(endpoint, content=malformed, headers={'Content-Type': 'application/json'})
                self.assertEqual(result.status_code, 422, result.text)
            self.assertEqual((await self.client.get(path)).json(), preserved)
        self.assertEqual((await self.client.patch(path, content='plain text', headers={'Content-Type': 'text/plain'})).status_code, 422)
        cleared = (await self.client.patch(path, json={'address': None})).json()
        self.assertIsNone(cleared['address'])
        self.assertEqual(cleared['coordinates'], preserved['coordinates'])
        cleared = (await self.client.patch(path, json={'coordinates': None})).json()
        self.assertEqual((cleared['location_id'], cleared['address'], cleared['coordinates']), (None, None, None))
        second, _ = await self.actor()
        self.assertEqual((await second.get(path)).json(), cleared)
        for locator in ({}, {'coordinates': {'latitude': 1, 'longitude': 2}}, {'location_id': None, 'address': None}):
            result = await self.client.post('/lockers', json={'compartments': payload['compartments']} | locator)
            self.assertEqual(result.status_code, 422, result.text)
        self.assertEqual((await self.client.post('/lockers')).status_code, 422)
        self.assertEqual((await self.client.patch(path)).status_code, 422)
        self.assertEqual((await self.client.patch(path, content='{')).status_code, 422)
        legacy = (await self.create()).json()
        self.assertEqual((legacy['location_id'], legacy['address'], legacy['coordinates']), ('Site', None, None))
