import unittest
from unittest.mock import AsyncMock

from application.use_cases import DeliveryService, ReturnService
from domain.ports import DeliveryRepository, ReturnRepository


class ApplicationTests(unittest.IsolatedAsyncioTestCase):
    async def test_delivery_normalizes_and_persists(self):
        repository = AsyncMock(spec=DeliveryRepository)
        delivery = await DeliveryService(repository).create("  Calle Mayor 1  ")
        self.assertEqual(delivery.address, "Calle Mayor 1")
        repository.save.assert_awaited_once_with(delivery)

    async def test_return_normalizes_and_persists(self):
        repository = AsyncMock(spec=ReturnRepository)
        item = await ReturnService(repository).create("  Producto dañado  ")
        self.assertEqual(item.reason, "Producto dañado")
        repository.save.assert_awaited_once_with(item)

    async def test_empty_values_are_rejected_before_persistence(self):
        for service_class, port in (
            (DeliveryService, DeliveryRepository),
            (ReturnService, ReturnRepository),
        ):
            for value in ("", " \t\n "):
                with self.subTest(service=service_class.__name__, value=value):
                    repository = AsyncMock(spec=port)
                    with self.assertRaises(ValueError):
                        await service_class(repository).create(value)
                    repository.save.assert_not_awaited()
