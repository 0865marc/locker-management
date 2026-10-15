import asyncio
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlmodel import SQLModel
from adapters.database.connection import create_database
from main import create_app

D = {'width_mm':10, 'height_mm':20, 'depth_mm':30}

class LockerHttpTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.url = f'sqlite+aiosqlite:///{Path(self.directory.name) / "lockers.sqlite"}'
        async def prepare():
            engine, _ = create_database(self.url)
            async with engine.begin() as connection:
                await connection.run_sync(SQLModel.metadata.create_all)
            await engine.dispose()
        asyncio.run(prepare())
        self.client = TestClient(create_app(self.url))
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)

    def create(self, **changes):
        return self.client.post('/lockers', json={'location_id':' Site ', 'compartments':[{'quantity':1, 'dimensions':D}]} | changes)

    def availability(self, **changes):
        return self.client.get('/lockers/availability', params={'location_id':'Site'} | D | changes)

    def test_configuration_endpoints_lifecycle_and_snapshot(self):
        self.assertEqual(self.availability().json()['reason'], 'NO_LOCKER')
        response = self.create()
        self.assertEqual(response.status_code,201,response.text)
        locker = response.json()
        self.assertEqual(locker['location_id'],'Site')
        self.assertEqual(locker['compartment_count'],1)
        identifier = locker['id']
        cell = locker['compartments'][0]
        self.assertEqual(set(cell), {'id','dimensions','enabled','occupied'})
        self.assertEqual(self.client.get('/lockers', params={'location_id':' Site '}).json(),[locker])
        self.assertEqual(self.client.get(f'/lockers/{identifier}').json(),locker)
        self.assertEqual(self.availability().json()['reason'],'AVAILABLE')
        self.assertEqual(self.availability(width_mm=100).json()['reason'],'NO_COMPATIBLE_CELL')
        changed = self.client.patch(f'/lockers/{identifier}/compartments/{cell["id"]}',json={'enabled':False})
        self.assertEqual(changed.status_code,200,changed.text)
        self.assertEqual(self.availability().json()['reason'],'NO_COMPATIBLE_CELL')
        added = self.client.post(f'/lockers/{identifier}/compartments',json={'compartments':[{'quantity':2,'dimensions':D}]})
        self.assertEqual(added.status_code,201,added.text)
        self.assertEqual(added.json()['compartment_count'],3)
        self.assertEqual(self.client.patch(f'/lockers/{identifier}',json={'active':False}).status_code,200)
        self.assertEqual(self.availability().json()['reason'],'LOCKER_INACTIVE')
        self.assertEqual(self.client.delete(f'/lockers/{identifier}/compartments/{cell["id"]}').status_code,204)
        self.assertEqual(self.client.delete(f'/lockers/{identifier}/compartments/{cell["id"]}').status_code,404)
        self.assertEqual(self.client.get(f'/lockers/{identifier}').json()['compartment_count'],2)

    def test_strict_validation_and_identity_errors(self):
        for location in (' ',1,True,None):
            self.assertEqual(self.create(location_id=location).status_code,422)
        for active in (1,'true',None):
            self.assertEqual(self.create(active=active).status_code,422)
        for invalid in (True,1.0,'1',0,-1,2147483648):
            for key in D:
                self.assertEqual(self.create(compartments=[{'quantity':1,'dimensions':D | {key:invalid}}]).status_code,422)
        for quantity in (True,1.0,'1',0,-1,1001):
            self.assertEqual(self.create(compartments=[{'quantity':quantity,'dimensions':D}]).status_code,422)
        for compartments in ([],[{'quantity':500,'dimensions':D},{'quantity':501,'dimensions':D}]):
            self.assertEqual(self.create(compartments=compartments).status_code,422)
        self.assertEqual(self.client.get('/lockers').json(),[])
        self.assertEqual(self.client.get('/lockers/not-uuid').status_code,422)
        self.assertEqual(self.client.get(f'/lockers/{uuid4()}').status_code,404)
        locker = self.create().json()
        identifier, cell = locker['id'], locker['compartments'][0]['id']
        for body in ({},{'active':1},{'active':True,'location_id':'Elsewhere'}):
            self.assertEqual(self.client.patch(f'/lockers/{identifier}',json=body).status_code,422)
        for body in ({},{'enabled':1},{'dimensions':None},{'enabled':None},{'occupied':False}):
            self.assertEqual(self.client.patch(f'/lockers/{identifier}/compartments/{cell}',json=body).status_code,422)
        for params in ({'width_mm':0},{'height_mm':'bad'},{'width_mm':'1.0'},{'depth_mm':'1e1'},{'depth_mm':2147483648},{'location_id':' '}):
            self.assertEqual(self.availability(**params).status_code,422)

    def test_delivery_return_reception_exit_reuse_and_historical_fields(self):
        locker = self.create().json()
        identifier, cell = locker['id'], locker['compartments'][0]['id']
        for flow, action in (('deliveries','collect'), ('deliveries','return-to-carrier'), ('returns','hand-over')):
            self.client.patch(f'/lockers/{identifier}',json={'active':True})
            self.client.patch(f'/lockers/{identifier}/compartments/{cell}',json={'dimensions':D})
            payload = {'tracking_number':'T','carrier_code':'C'}
            if flow == 'deliveries':
                payload['recipient_name'] = 'Ana'
            for invalid in ({'locker_id':identifier},{'parcel_dimensions':D},{'compartment_id':cell}):
                self.assertEqual(self.client.post(f'/{flow}',json=payload | invalid).status_code,422)
            unknown = self.client.post(f'/{flow}',json=payload | {'locker_id':str(uuid4()),'parcel_dimensions':D})
            self.assertEqual(unknown.status_code,404,unknown.text)
            received = self.client.post(f'/{flow}',json=payload | {'locker_id':identifier,'parcel_dimensions':D})
            self.assertEqual(received.status_code,201,received.text)
            parcel = received.json()
            self.assertEqual(parcel['compartment_id'],cell)
            self.assertEqual(parcel['parcel_dimensions'],D)
            full = self.client.post('/returns',json={'tracking_number':'R','carrier_code':'C','locker_id':identifier,'parcel_dimensions':D})
            self.assertEqual(full.status_code,409,full.text)
            self.assertEqual(full.json()['detail']['code'],'FULL')
            self.assertEqual(self.availability().json()['reason'],'FULL')
            for method, body in (('patch',{'enabled':False}),('patch',{'dimensions':D}),('delete',None)):
                result = getattr(self.client, method)(f'/lockers/{identifier}/compartments/{cell}',**({'json':body} if body else {}))
                self.assertEqual(result.status_code,409,result.text)
            self.client.patch(f'/lockers/{identifier}',json={'active':False})
            exited = self.client.post(f'/{flow}/{parcel["id"]}/{action}')
            self.assertEqual(exited.status_code,200,exited.text)
            self.assertEqual(exited.json()['parcel_dimensions'],D)
            self.client.patch(f'/lockers/{identifier}',json={'active':True})
            occupant = self.client.post('/returns',json={'tracking_number':'B','carrier_code':'C','locker_id':identifier,'parcel_dimensions':D}).json()
            self.assertEqual(self.client.post(f'/{flow}/{parcel["id"]}/{action}').status_code,409)
            self.assertEqual(self.availability().json()['reason'],'FULL')
            self.assertEqual(self.client.post(f'/returns/{occupant["id"]}/hand-over').status_code,200)
            self.client.patch(f'/lockers/{identifier}/compartments/{cell}',json={'dimensions':{'width_mm':1,'height_mm':1,'depth_mm':1}})
            self.assertIn(exited.json(), self.client.get(f'/{flow}').json())
        self.assertEqual(self.client.delete(f'/lockers/{identifier}/compartments/{cell}').status_code,204)
        for path in ('/deliveries','/returns'):
            for record in self.client.get(path).json():
                self.assertEqual(record['compartment_id'],cell)
                self.assertEqual(record['parcel_dimensions'],D)
