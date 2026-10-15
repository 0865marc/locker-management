import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timezone
from uuid import UUID, uuid4
from domain.lockers import Dimensions, Compartment, CompartmentBatch, Locker, select_compartment, validate_batches
from domain.models import Delivery, Return

class LockerDomainTests(unittest.TestCase):
    def test_integer_ranges_rotation_and_axis_fit(self):
        for invalid in (True, False, 1.0, '1', 0, -1, 2147483648, None):
            for axis in range(3):
                values = [1, 1, 1]
                values[axis] = invalid
                with self.subTest(values=values), self.assertRaises(ValueError):
                    Dimensions(*values)
        self.assertTrue(Dimensions(30, 10, 20).fits_in(Dimensions(10, 20, 30)))
        self.assertFalse(Dimensions(1, 1, 31).fits_in(Dimensions(10, 20, 30)))
        self.assertEqual(Dimensions(2147483647, 2147483647, 2147483647).volume, 2147483647 ** 3)
        self.assertEqual(Dimensions(1, 2, 3), Dimensions(1, 2, 3))

    def test_selection_minimum_volume_uuid_and_exclusions(self):
        locker = uuid4()
        small = Compartment(locker, Dimensions(3, 2, 1), id=UUID(int=1))
        same = replace(small, id=UUID(int=2))
        large = replace(small, dimensions=Dimensions(4, 4, 4), id=UUID(int=0))
        for excluded in (replace(small, occupied=True), replace(small, enabled=False), replace(small, enabled=False, retired=True)):
            self.assertEqual(select_compartment([large, same, excluded], Dimensions(1, 2, 3)), same)
        self.assertEqual(select_compartment([large, same, small], Dimensions(1, 2, 3)), small)
        self.assertIsNone(select_compartment([small], Dimensions(4, 1, 1)))

    def test_batches_locations_booleans_and_immutable_values(self):
        dimensions = Dimensions(1, 2, 3)
        for invalid in (True, 0, -1, 1.5, '1'):
            with self.assertRaises(ValueError):
                CompartmentBatch(invalid, dimensions)
        with self.assertRaises(ValueError):
            validate_batches([CompartmentBatch(500, dimensions), CompartmentBatch(501, dimensions)])
        with self.assertRaises(ValueError):
            validate_batches([])
        self.assertEqual(Locker(' Site ').location_id, 'Site')
        for invalid in (' ', None, 1):
            with self.assertRaises(ValueError):
                Locker(invalid)
        with self.assertRaises(FrozenInstanceError):
            dimensions.width_mm = 2

    def test_parcel_assignment_requires_complete_values_and_survives_transitions(self):
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
