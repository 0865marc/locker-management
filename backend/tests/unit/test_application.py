import unittest
from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

from application.delivery_use_cases import DeliveryService
from application.errors import ParcelNotFoundError
from application.return_use_cases import ReturnService
from domain.lockers import Dimensions
from domain.validation import CustodyConflictError
from domain.deliveries import Delivery, DeliveryStatus
from domain.returns import Return, ReturnStatus
from domain.ports import DeliveryRepository, ReturnRepository


RECEIVED = datetime(2026, 10, 14, 10, tzinfo=timezone.utc)
EXIT = RECEIVED + timedelta(hours=1)


async def create_parcel(
    service: DeliveryService | ReturnService,
    args: Sequence[str],
    *,
    locker_id: UUID | None = None,
    parcel_dimensions: Dimensions | None = None,
) -> Delivery | Return:
    """Dispatch heterogeneous fixtures with each service's real positional contract."""
    if isinstance(service, DeliveryService):
        return await service.create(args[0], args[1], args[2],
                                    locker_id=locker_id, parcel_dimensions=parcel_dimensions)
    return await service.create(args[0], args[1],
                                locker_id=locker_id, parcel_dimensions=parcel_dimensions)


class ApplicationTests(unittest.IsolatedAsyncioTestCase):
    def cases(self) -> tuple[tuple[type[DeliveryService] | type[ReturnService], object, Delivery | Return, str, DeliveryStatus | ReturnStatus, str], ...]:
        # The protocol objects are Mock specs, not concrete classes to instantiate.
        return (
            (DeliveryService, DeliveryRepository, Delivery(tracking_number="D", carrier_code="C", recipient_name="Ana", received_at=RECEIVED), "collect", DeliveryStatus.COLLECTED, "collected_at"),
            (DeliveryService, DeliveryRepository, Delivery(tracking_number="D", carrier_code="C", recipient_name="Ana", received_at=RECEIVED), "return_to_carrier", DeliveryStatus.RETURNED_TO_CARRIER, "returned_to_carrier_at"),
            (ReturnService, ReturnRepository, Return(tracking_number="R", carrier_code="C", received_at=RECEIVED), "hand_over", ReturnStatus.HANDED_OVER, "handed_over_at"),
        )

    async def test_delivery_normalizes_and_persists_with_injected_clock(self) -> None:
        repository = AsyncMock(spec=DeliveryRepository)
        clock = Mock(return_value=RECEIVED)
        deadline = (RECEIVED - timedelta(days=1)).astimezone(timezone(timedelta(hours=2)))
        delivery = await DeliveryService(repository, clock).create(" PKG-42 ", " carrier-a ", " Ana García ", " +34 600 ", deadline)
        self.assertEqual((delivery.tracking_number, delivery.carrier_code, delivery.recipient_name, delivery.recipient_phone), ("PKG-42", "carrier-a", "Ana García", "+34 600"))
        self.assertEqual(delivery.received_at, RECEIVED)
        assert delivery.pickup_deadline_at is not None
        self.assertIs(delivery.pickup_deadline_at.tzinfo, timezone.utc)
        repository.save.assert_awaited_once_with(delivery)
        repository.save_exit.assert_not_awaited()
        clock.assert_called_once_with()

    async def test_return_normalizes_and_persists_independently(self) -> None:
        repository = AsyncMock(spec=ReturnRepository)
        item = await ReturnService(repository, lambda: RECEIVED).create(" PKG-42 ", " carrier-a ", " Luis ")
        self.assertEqual((item.tracking_number, item.carrier_code, item.sender_name), ("PKG-42", "carrier-a", "Luis"))
        self.assertEqual(item.received_at, RECEIVED)
        repository.save.assert_awaited_once_with(item)
        repository.get_by_id.assert_not_awaited()

    async def test_default_clock_assigns_aware_utc_reception(self) -> None:
        for service_class, port, args in ((DeliveryService, DeliveryRepository, ("D", "C", "Ana")), (ReturnService, ReturnRepository, ("R", "C"))):
            repository = AsyncMock(spec=port)
            item = await create_parcel(service_class(repository), args)
            self.assertIs(item.received_at.tzinfo, timezone.utc)

    async def test_invalid_creation_never_writes(self) -> None:
        for service_class, port, args in ((DeliveryService, DeliveryRepository, ["D", "C", "Ana"]), (ReturnService, ReturnRepository, ["R", "C"])):
            for index in range(len(args)):
                for bad in ("", " \t\n "):
                    with self.subTest(service=service_class.__name__, index=index, value=bad):
                        repository = AsyncMock(spec=port)
                        invalid = args.copy()
                        invalid[index] = bad
                        with self.assertRaises(ValueError):
                            await create_parcel(service_class(repository, lambda: RECEIVED), invalid)
                        repository.save.assert_not_awaited()
                        repository.save_exit.assert_not_awaited()
        repository = AsyncMock(spec=DeliveryRepository)
        with self.assertRaises(ValueError):
            await DeliveryService(repository, lambda: RECEIVED).create("D", "C", "Ana", pickup_deadline_at=RECEIVED.replace(tzinfo=None))
        repository.save.assert_not_awaited()

    async def test_lists_delegate_to_the_correct_repository(self) -> None:
        for service_class, port, item, *_ in self.cases():
            repository = AsyncMock(spec=port)
            repository.list_all.return_value = [item]
            self.assertEqual(await service_class(repository).list_all(), [item])
            repository.list_all.assert_awaited_once_with()
            repository.save.assert_not_awaited()

    async def test_successful_exits_use_clock_and_persist_before_returning(self) -> None:
        for service_class, port, item, method, status, field in self.cases():
            with self.subTest(method=method):
                repository = AsyncMock(spec=port)
                repository.get_by_id.return_value = item
                repository.save_exit.return_value = True
                updated = await getattr(service_class(repository, lambda: EXIT), method)(item.id)
                repository.get_by_id.assert_awaited_once_with(item.id)
                repository.save_exit.assert_awaited_once_with(updated)
                repository.save.assert_not_awaited()
                self.assertEqual(updated.status, status)
                self.assertEqual(getattr(updated, field), EXIT)
                self.assertEqual(updated.id, item.id)
                self.assertIsNone(getattr(item, field))

    async def test_unknown_parcels_raise_typed_absence_without_writes_or_clock(self) -> None:
        for service_class, port, _, method, *_ in self.cases():
            repository = AsyncMock(spec=port)
            repository.get_by_id.return_value = None
            clock = Mock(return_value=EXIT)
            with self.assertRaises(ParcelNotFoundError):
                await getattr(service_class(repository, clock), method)(uuid4())
            repository.save.assert_not_awaited()
            repository.save_exit.assert_not_awaited()
            clock.assert_not_called()

    async def test_repeated_incompatible_and_backwards_exits_never_write(self) -> None:
        for service_class, port, item, method, *_ in self.cases():
            terminal = getattr(item, method)(EXIT)
            invalid_items = [terminal]
            if isinstance(item, Delivery):
                opposite = "return_to_carrier" if method == "collect" else "collect"
                invalid_items.append(getattr(item, opposite)(EXIT))
            for stored in invalid_items:
                repository = AsyncMock(spec=port)
                repository.get_by_id.return_value = stored
                with self.assertRaises(CustodyConflictError):
                    await getattr(service_class(repository, lambda: EXIT), method)(item.id)
                repository.save_exit.assert_not_awaited()
                repository.save.assert_not_awaited()
            repository = AsyncMock(spec=port)
            repository.get_by_id.return_value = item
            with self.assertRaises(CustodyConflictError):
                await getattr(service_class(repository, lambda: RECEIVED - timedelta(seconds=1)), method)(item.id)
            repository.save_exit.assert_not_awaited()

    async def test_conditional_write_loss_becomes_conflict_and_preserves_input(self) -> None:
        for service_class, port, item, method, *_ in self.cases():
            repository = AsyncMock(spec=port)
            repository.get_by_id.return_value = item
            repository.save_exit.return_value = False
            with self.assertRaises(CustodyConflictError):
                await getattr(service_class(repository, lambda: EXIT), method)(item.id)
            repository.save_exit.assert_awaited_once()
            repository.save.assert_not_awaited()
            self.assertIn(item.status, (DeliveryStatus.AWAITING_PICKUP, ReturnStatus.AWAITING_CARRIER))

    async def test_infrastructure_failures_are_propagated(self) -> None:
        for service_class, port, item, method, *_ in self.cases():
            repository = AsyncMock(spec=port)
            repository.get_by_id.return_value = item
            error = RuntimeError("commit failed")
            repository.save_exit.side_effect = error
            with self.assertRaises(RuntimeError) as caught:
                await getattr(service_class(repository, lambda: EXIT), method)(item.id)
            self.assertIs(caught.exception, error)
        repository = AsyncMock(spec=ReturnRepository)
        repository.save.side_effect = RuntimeError("insert failed")
        with self.assertRaises(RuntimeError):
            await ReturnService(repository, lambda: RECEIVED).create("R", "C")

    async def test_locker_reception_returns_repository_complete_entity_without_save(self) -> None:
        from dataclasses import replace
        from domain.lockers import Dimensions
        for service_class, port, args in ((DeliveryService, DeliveryRepository, ('D','C','Ana')), (ReturnService, ReturnRepository, ('R','C'))):
            repository = AsyncMock(spec=port)
            locker_id, cell_id = uuid4(), uuid4()
            dimensions = Dimensions(10,20,30)
            async def receive(entity: Delivery | Return, identifier: UUID, parcel_dimensions: Dimensions) -> Delivery | Return:
                self.assertIsNone(entity.locker_id)
                self.assertIsNone(entity.compartment_id)
                self.assertIsNone(entity.parcel_dimensions)
                return replace(entity, locker_id=identifier, compartment_id=cell_id, parcel_dimensions=parcel_dimensions)
            repository.receive_in_locker.side_effect = receive
            result = await create_parcel(service_class(repository, lambda: RECEIVED), args, locker_id=locker_id, parcel_dimensions=dimensions)
            repository.save.assert_not_awaited()
            repository.receive_in_locker.assert_awaited_once()
            self.assertEqual((result.locker_id, result.compartment_id, result.parcel_dimensions), (locker_id,cell_id,dimensions))
            for partial_locker, partial_dimensions in ((locker_id, None), (None, dimensions)):
                repository.reset_mock()
                with self.assertRaises(ValueError):
                    await create_parcel(service_class(repository, lambda: RECEIVED), args, locker_id=partial_locker, parcel_dimensions=partial_dimensions)
                repository.save.assert_not_awaited()
                repository.receive_in_locker.assert_not_awaited()

    async def test_locker_service_validates_batches_before_repository(self) -> None:
        from application.locker_use_cases import LockerService
        from domain.lockers import Dimensions, CompartmentBatch
        from domain.ports import LockerRepository
        repository = AsyncMock(spec=LockerRepository)
        service = LockerService(repository)
        for batches in ([], [CompartmentBatch(1001,Dimensions(1,2,3))]):
            with self.assertRaises(ValueError):
                await service.create('Site',batches)
            repository.create.assert_not_awaited()
            with self.assertRaises(ValueError):
                await service.add_compartments(uuid4(),batches)
            repository.add_compartments.assert_not_awaited()
        batches = [CompartmentBatch(2,Dimensions(1,2,3))]
        await service.create(' Site ', batches)
        repository.create.assert_awaited_once_with('Site',batches,True)
