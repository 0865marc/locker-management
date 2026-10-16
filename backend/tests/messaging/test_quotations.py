"""Isolated PostgreSQL/RabbitMQ smoke; explicit configuration is mandatory."""
import asyncio
from contextlib import suppress
from datetime import datetime, timezone
import os
from uuid import uuid4

import aio_pika
from aio_pika.abc import AbstractIncomingMessage

from adapters.database.sqlmodel_quotations import SqlModelQuotationRepository
from adapters.providers.simulated_shipping import SimulatedEconomyProvider
from adapters.queue.rabbitmq import RabbitMQ, handle_delivery
from application.quotation_models import QuotationStatus
from application.quotations import QuotationService, QuotationProcessor
from application.shipping_quotes import ShippingQuoteService, ProviderStatus, ProviderErrorCode
from domain.shipping_quotes import ShippingQuoteRequest, QuoteOffers, NoCoverage
from domain.lockers import Dimensions
from tests.integration.support import PostgresTestCase


def rabbitmq_url() -> str:
    value = os.getenv('TEST_RABBITMQ_URL', '').strip()
    if not value:
        raise RuntimeError('TEST_RABBITMQ_URL is required for messaging smoke tests')
    from urllib.parse import urlparse
    try:
        parsed = urlparse(value)
        if parsed.scheme not in ('amqp', 'amqps') or not parsed.hostname:
            raise ValueError()
        parsed.port
    except ValueError:
        raise RuntimeError('TEST_RABBITMQ_URL must be a valid AMQP URL') from None
    return value


class ObservedDelivery:
    def __init__(self, message: AbstractIncomingMessage, events: list[str]) -> None:
        self.message = message
        self.events = events

    @property
    def body(self) -> bytes:
        return self.message.body

    async def ack(self) -> None:
        await self.message.ack()
        self.events.append('ack')


class ControlledProvider:
    def __init__(self, code: str, outcome: str, events: list[str]) -> None:
        self.code = code
        self.outcome = outcome
        self.events = events
        self.calls = 0

    async def quote(self, request: ShippingQuoteRequest) -> QuoteOffers | NoCoverage:
        if not self.events or self.events[0] != 'ack':
            raise AssertionError('Provider called before acknowledgement')
        self.events.append(self.code)
        self.calls += 1
        if self.outcome == 'error':
            raise RuntimeError('Controlled provider error')
        if self.outcome == 'timeout':
            await asyncio.Event().wait()
        if self.outcome == 'uncovered':
            return NoCoverage()
        return await SimulatedEconomyProvider().quote(request)


class MessagingSmokeTests(PostgresTestCase):
    @classmethod
    def setUpClass(cls):
        cls.broker_url = rabbitmq_url()
        super().setUpClass()

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.broker = RabbitMQ(self.broker_url, 'test.shipping.quotations.' + uuid4().hex)
        self.resources.push_async_callback(self.broker.close)
        try:
            await self.broker.open()
        except Exception:
            raise RuntimeError('RabbitMQ smoke preflight failed: check test broker connectivity and credentials') from None
        self.resources.push_async_callback(self.remove_queue)

    async def remove_queue(self):
        if self.broker.queue is not None:
            await self.broker.queue.delete(if_unused=False, if_empty=False)

    async def test_confirmed_publication_early_ack_persistence_and_no_requeue(self):
        events = []
        providers = tuple(ControlledProvider(code, outcome, events) for code, outcome in
            (('success', 'success'), ('error', 'error'), ('timeout', 'timeout'), ('uncovered', 'uncovered')))
        repository = SqlModelQuotationRepository(self.sessions)
        processor = QuotationProcessor(repository, ShippingQuoteService(providers, timeout_seconds=.03),
                                       lambda: datetime.now(timezone.utc))
        service = QuotationService(repository, self.broker, lambda: datetime.now(timezone.utc))
        item = await service.submit(ShippingQuoteRequest('ES', '01001', 'ES', '28001', 1200, Dimensions(200, 150, 100)))
        pending = await repository.get(item.id)
        assert pending is not None
        self.assertEqual(pending.status, QuotationStatus.PENDING)
        assert self.broker.queue is not None
        message = await self.broker.queue.get(timeout=5)
        assert message is not None
        self.assertFalse(message.redelivered)
        await handle_delivery(ObservedDelivery(message, events), processor)
        self.assertTrue(message.processed)
        _, sessions = self.database()
        stored = await SqlModelQuotationRepository(sessions).get(item.id)
        assert stored is not None
        self.assertEqual(stored.status, QuotationStatus.COMPLETED)
        self.assertEqual([result.status for result in stored.results],
            [ProviderStatus.FAILED, ProviderStatus.QUOTED, ProviderStatus.FAILED, ProviderStatus.NOT_COVERED])
        self.assertEqual([result.error_code for result in stored.results],
            [ProviderErrorCode.PROVIDER_ERROR, None, ProviderErrorCode.PROVIDER_TIMEOUT, None])
        self.assertEqual([provider.calls for provider in providers], [1, 1, 1, 1])
        # Close/reopen the ordinary consumer connection; acknowledged work cannot reappear.
        await self.broker.close()
        await self.broker.open()
        assert self.broker.queue is not None
        assert self.broker.channel is not None
        self.assertIsNone(await self.broker.queue.get(fail=False))
        # Real sequential consume path ignores a duplicate completed id and malformed input.
        await self.broker.publish(item.id)
        await self.broker.channel.default_exchange.publish(aio_pika.Message(b'invalid'), routing_key=self.broker.queue_name)
        consumer = asyncio.create_task(self.broker.consume(processor))
        try:
            async with asyncio.timeout(5):
                while True:
                    queue = await self.broker.channel.declare_queue(self.broker.queue_name, passive=True)
                    if queue.declaration_result.message_count == 0:
                        break
                    await asyncio.sleep(.01)
        finally:
            consumer.cancel()
            with suppress(asyncio.CancelledError):
                await consumer
        self.assertIsNone(await self.broker.queue.get(fail=False))
        self.assertEqual([provider.calls for provider in providers], [1, 1, 1, 1])
