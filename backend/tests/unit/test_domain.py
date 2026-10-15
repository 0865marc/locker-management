import unittest
from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
from uuid import UUID

from domain.validation import CustodyConflictError
from domain.deliveries import Delivery, DeliveryStatus
from domain.returns import Return, ReturnStatus


RECEIVED = datetime(2026, 10, 14, 10, tzinfo=timezone.utc)
EXIT = RECEIVED + timedelta(hours=1)


def delivery(**overrides: object) -> Delivery:
    # replace is a dynamic dataclass fixture boundary, including deliberately invalid inputs.
    return replace(Delivery(" PKG-42 ", " carrier-a ", " Ana García ", RECEIVED), **overrides)


def return_parcel(**overrides: object) -> Return:
    return replace(Return(" PKG-42 ", " carrier-a ", RECEIVED), **overrides)


class DomainTests(unittest.TestCase):
    def test_initial_parcels_are_normalized_independent_and_immutable(self) -> None:
        first, second = delivery(), return_parcel()
        for item in (first, second):
            self.assertIsInstance(item.id, UUID)
            self.assertEqual(item.tracking_number, "PKG-42")
            self.assertEqual(item.carrier_code, "carrier-a")
            self.assertEqual(item.received_at, RECEIVED)
            self.assertIs(item.received_at.tzinfo, timezone.utc)
            with self.assertRaises(FrozenInstanceError):
                setattr(item, "tracking_number", "changed")
        self.assertNotEqual(first.id, second.id)
        self.assertEqual(first.recipient_name, "Ana García")
        self.assertEqual(first.status, DeliveryStatus.AWAITING_PICKUP)
        self.assertIsNone(first.recipient_phone)
        self.assertIsNone(first.pickup_deadline_at)
        self.assertIsNone(first.collected_at)
        self.assertIsNone(first.returned_to_carrier_at)
        self.assertEqual(second.status, ReturnStatus.AWAITING_CARRIER)
        self.assertIsNone(second.sender_name)
        self.assertIsNone(second.handed_over_at)
        self.assertFalse(hasattr(first, "address"))
        self.assertFalse(hasattr(second, "reason"))
        self.assertFalse(hasattr(second, "delivery_id"))

    def test_optional_text_and_all_instants_normalize(self) -> None:
        offset = timezone(timedelta(hours=2))
        item = delivery(recipient_phone=" +34 600 123 ", received_at=RECEIVED.astimezone(offset), pickup_deadline_at=(RECEIVED - timedelta(days=1)).astimezone(offset))
        self.assertEqual(item.recipient_phone, "+34 600 123")
        self.assertIs(item.received_at.tzinfo, timezone.utc)
        assert item.pickup_deadline_at is not None
        self.assertIs(item.pickup_deadline_at.tzinfo, timezone.utc)
        self.assertEqual(item.pickup_deadline_at, RECEIVED - timedelta(days=1))
        self.assertIsNone(delivery(recipient_phone=" \n ").recipient_phone)
        self.assertEqual(return_parcel(sender_name=" Luis  Pérez ").sender_name, "Luis  Pérez")
        self.assertIsNone(return_parcel(sender_name=" \t ").sender_name)
        collected = item.collect(EXIT.astimezone(offset))
        handed = return_parcel(received_at=RECEIVED.astimezone(offset)).hand_over(EXIT.astimezone(offset))
        assert collected.collected_at is not None
        self.assertIs(collected.collected_at.tzinfo, timezone.utc)
        assert handed.handed_over_at is not None
        self.assertIs(handed.handed_over_at.tzinfo, timezone.utc)

    def test_required_text_rejects_blanks_and_incorrect_types(self) -> None:
        for factory, names in ((delivery, ("tracking_number", "carrier_code", "recipient_name")), (return_parcel, ("tracking_number", "carrier_code"))):
            for name in names:
                for value in ("", " \n ", None, 4, []):
                    with self.subTest(factory=factory.__name__, name=name, value=value):
                        with self.assertRaises(ValueError):
                            factory(**{name: value})
        for factory, name in ((delivery, "recipient_phone"), (return_parcel, "sender_name")):
            with self.assertRaises(ValueError):
                factory(**{name: 123})

    def test_naive_instants_are_invalid_including_reconstruction(self) -> None:
        naive = RECEIVED.replace(tzinfo=None)
        for factory in (delivery, return_parcel):
            with self.assertRaises(ValueError):
                factory(received_at=naive)
        with self.assertRaises(ValueError):
            delivery(pickup_deadline_at=naive)
        with self.assertRaises(ValueError):
            delivery(status=DeliveryStatus.COLLECTED, collected_at=naive)
        with self.assertRaises(ValueError):
            return_parcel(status=ReturnStatus.HANDED_OVER, handed_over_at=naive)

    def test_delivery_exits_preserve_original_and_are_exclusive(self) -> None:
        original = delivery(pickup_deadline_at=RECEIVED - timedelta(days=1))
        for method, status, field in (("collect", DeliveryStatus.COLLECTED, "collected_at"), ("return_to_carrier", DeliveryStatus.RETURNED_TO_CARRIER, "returned_to_carrier_at")):
            with self.subTest(method=method):
                updated = getattr(original, method)(EXIT)
                self.assertEqual(updated.id, original.id)
                self.assertEqual(updated.received_at, original.received_at)
                self.assertEqual(updated.status, status)
                self.assertEqual(getattr(updated, field), EXIT)
                self.assertEqual(original.status, DeliveryStatus.AWAITING_PICKUP)
                self.assertIsNone(original.collected_at)
                self.assertIsNone(original.returned_to_carrier_at)
                for repeated in ("collect", "return_to_carrier"):
                    with self.assertRaises(CustodyConflictError):
                        getattr(updated, repeated)(EXIT + timedelta(hours=1))
                self.assertEqual(getattr(updated, field), EXIT)

    def test_return_handover_preserves_original_and_rejects_repetition(self) -> None:
        original = return_parcel()
        updated = original.hand_over(EXIT)
        self.assertEqual(updated.id, original.id)
        self.assertEqual(updated.status, ReturnStatus.HANDED_OVER)
        self.assertEqual(updated.handed_over_at, EXIT)
        self.assertEqual(original.status, ReturnStatus.AWAITING_CARRIER)
        self.assertIsNone(original.handed_over_at)
        with self.assertRaises(CustodyConflictError):
            updated.hand_over(EXIT + timedelta(hours=1))
        self.assertEqual(updated.handed_over_at, EXIT)

    def test_exits_reject_backwards_time_and_accept_reception_time(self) -> None:
        for item, method in ((delivery(), "collect"), (delivery(), "return_to_carrier"), (return_parcel(), "hand_over")):
            with self.subTest(method=method):
                with self.assertRaises(CustodyConflictError):
                    getattr(item, method)(RECEIVED - timedelta(microseconds=1))
                getattr(item, method)(RECEIVED)

    def test_reconstruction_rejects_incompatible_status_dates_and_chronology(self) -> None:
        for status in DeliveryStatus:
            for collected in (None, EXIT):
                for returned in (None, EXIT):
                    valid = (collected is not None, returned is not None) == {
                        DeliveryStatus.AWAITING_PICKUP: (False, False),
                        DeliveryStatus.COLLECTED: (True, False),
                        DeliveryStatus.RETURNED_TO_CARRIER: (False, True),
                    }[status]
                    with self.subTest(status=status, collected=collected, returned=returned):
                        if valid:
                            delivery(status=status, collected_at=collected, returned_to_carrier_at=returned)
                        else:
                            with self.assertRaises(ValueError):
                                delivery(status=status, collected_at=collected, returned_to_carrier_at=returned)
        for status, at in ((ReturnStatus.AWAITING_CARRIER, EXIT), (ReturnStatus.HANDED_OVER, None)):
            with self.assertRaises(ValueError):
                return_parcel(status=status, handed_over_at=at)
        earlier = RECEIVED - timedelta(seconds=1)
        for factory, values in ((delivery, dict(status=DeliveryStatus.COLLECTED, collected_at=earlier)), (delivery, dict(status=DeliveryStatus.RETURNED_TO_CARRIER, returned_to_carrier_at=earlier)), (return_parcel, dict(status=ReturnStatus.HANDED_OVER, handed_over_at=earlier))):
            with self.assertRaises(ValueError):
                factory(**values)
        for item in (delivery(), return_parcel()):
            with self.assertRaises(ValueError):
                replace(item, status="UNKNOWN")
