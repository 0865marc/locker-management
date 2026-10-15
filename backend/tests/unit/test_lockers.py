import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from uuid import UUID, uuid4
from domain.lockers import Dimensions, Compartment, CompartmentBatch, Locker, select_compartment, validate_batches
from domain.deliveries import Delivery
from domain.returns import Return

class LockerDomainTests(unittest.TestCase):
    def test_integer_ranges_rotation_and_axis_fit(self) -> None:
        for invalid in (True, False, 1.0, '1', 0, -1, 2147483648, None):
            for axis in range(3):
                values: list[object] = [1, 1, 1]
                values[axis] = invalid
                with self.subTest(values=values):
                    self.assertRaises(ValueError, Dimensions, *values)
        self.assertTrue(Dimensions(30, 10, 20).fits_in(Dimensions(10, 20, 30)))
        self.assertFalse(Dimensions(1, 1, 31).fits_in(Dimensions(10, 20, 30)))
        self.assertEqual(Dimensions(2147483647, 2147483647, 2147483647).volume, 2147483647 ** 3)
        self.assertEqual(Dimensions(1, 2, 3), Dimensions(1, 2, 3))

    def test_selection_minimum_volume_uuid_and_exclusions(self) -> None:
        locker = uuid4()
        small = Compartment(locker, Dimensions(3, 2, 1), id=UUID(int=1))
        same = replace(small, id=UUID(int=2))
        large = replace(small, dimensions=Dimensions(4, 4, 4), id=UUID(int=0))
        for excluded in (replace(small, occupied=True), replace(small, enabled=False), replace(small, enabled=False, retired=True)):
            self.assertEqual(select_compartment([large, same, excluded], Dimensions(1, 2, 3)), same)
        self.assertEqual(select_compartment([large, same, small], Dimensions(1, 2, 3)), small)
        self.assertIsNone(select_compartment([small], Dimensions(4, 1, 1)))

    def test_batches_locations_booleans_and_immutable_values(self) -> None:
        dimensions = Dimensions(1, 2, 3)
        for invalid in (True, 0, -1, 1.5, '1'):
            self.assertRaises(ValueError, CompartmentBatch, invalid, dimensions)
        with self.assertRaises(ValueError):
            validate_batches([CompartmentBatch(500, dimensions), CompartmentBatch(501, dimensions)])
        with self.assertRaises(ValueError):
            validate_batches([])
        self.assertEqual(Locker(' Site ').location_id, 'Site')
        for invalid in (' ', 1):
            self.assertRaises(ValueError, Locker, invalid)
        with self.assertRaises(FrozenInstanceError):
            setattr(dimensions, 'width_mm', 2)

    def test_parcel_assignment_requires_complete_values_and_survives_transitions(self) -> None:
        at = datetime.now(timezone.utc)
        for item, actions in ((Delivery('T', 'C', 'N', at), ('collect', 'return_to_carrier')), (Return('T', 'C', at), ('hand_over',))):
            assignment = dict(locker_id=uuid4(), compartment_id=uuid4(), parcel_dimensions=Dimensions(1, 2, 3))
            for missing in assignment:
                partial = assignment | {missing: None}
                with self.assertRaises(ValueError):
                    replace(item, **partial)
            complete = replace(item, **assignment)
            for action in actions:
                exited = getattr(complete, action)(at)
                for name, value in assignment.items():
                    self.assertEqual(getattr(exited, name), value)

    def test_address_coordinates_and_nullable_reconstruction(self) -> None:
        from domain.lockers import Address, Coordinates
        address = Address('ES', '01001', ' Araba ', ' Vitoria ', ' Calle ', ' 12B ')
        self.assertEqual((address.postal_code, address.street_number), ('01001', '12B'))
        self.assertEqual(address.province, 'Araba')
        self.assertEqual(Address('ES', '01001', 'P', 'C', 'S', 's/n').street_number, 's/n')
        self.assertIsNone(Locker(address=address).location_id)
        self.assertIsNone(Locker().address)  # Valid reconstruction after administrative clearing.
        for postal in ('1001', '010010', '０１００１', ' 01001', 1001):
            self.assertRaises(ValueError, Address, 'ES', postal, 'P', 'C', 'S', 'N')
        for invalid in ('', ' ', None, 1):
            self.assertRaises(ValueError, Address, 'ES', '01001', invalid, 'C', 'S', 'N')
        with self.assertRaises(ValueError):
            Address('FR', '01001', 'P', 'C', 'S', 'N')
        self.assertEqual(Coordinates(-90, 180), Coordinates(-90.0, 180.0))
        for latitude, longitude in ((91,0), (0,181), (float('nan'),0), (0,float('inf')), (True,0), ('1',0), (10**400, 0)):
            self.assertRaises(ValueError, Coordinates, latitude, longitude)

    def test_geography_http_schema_creation_and_patch_contract(self) -> None:
        from pydantic import ValidationError
        from adapters.http.locker_schemas import CreateLocker, UpdateLocker
        address = dict(country_code='ES', postal_code='01001', province='P', city='C', street='S', street_number='s/n')
        batches = [dict(quantity=1, dimensions=dict(width_mm=1, height_mm=2, depth_mm=3))]
        self.assertIsNone(CreateLocker.model_validate({'compartments': batches, 'address': address}).location_id)
        self.assertIsNone(CreateLocker.model_validate({'compartments': batches, 'location_id': 'Legacy'}).address)
        for body in ({}, {'coordinates': {'latitude': 0, 'longitude': 0}}, {'location_id': None}):
            with self.assertRaises(ValidationError):
                CreateLocker.model_validate(dict(compartments=batches) | body)
        for body in ({}, {'active': None}, {'address': {'country_code': 'ES'}}, {'coordinates': {'latitude': 0}}, {'location_id': 'X'}):
            with self.assertRaises(ValidationError):
                UpdateLocker.model_validate(body)
        active = UpdateLocker(active=False).domain()
        self.assertFalse(active.address_supplied)
        self.assertFalse(active.coordinates_supplied)
        cleared = UpdateLocker(address=None).domain()
        self.assertTrue(cleared.address_supplied)
        self.assertIsNone(cleared.address)
        replacement = UpdateLocker.model_validate({'address': address, 'coordinates': {'latitude': 90, 'longitude': -180}}).domain()
        assert replacement.address is not None
        self.assertEqual(replacement.address.postal_code, '01001')
        self.assertTrue(replacement.coordinates_supplied)
