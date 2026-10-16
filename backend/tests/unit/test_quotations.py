"""Infrastructure-free quotation orchestration, HTTP and acknowledgement checks."""
import asyncio
from dataclasses import replace
from datetime import datetime, timezone
import json
import unittest
from unittest.mock import AsyncMock
from uuid import uuid4

from fastapi import FastAPI
import httpx

from adapters.http.quotations.routes import create_quotation_router
from adapters.queue.rabbitmq import handle_delivery, RabbitMQ
from application.quotation_models import (Quotation, QuotationStatus, ProcessErrorCode,
    PublicationError, QuotationStorageError, SubmissionError)
from application.quotation_ports import QuotationRepository, QuotationPublisher
from application.quotations import QuotationService, QuotationProcessor
from application.shipping_quotes import ShippingQuoteService, ProviderResult, ProviderStatus, ProviderErrorCode
from domain.lockers import Dimensions
from domain.shipping_quotes import ShippingQuoteRequest
from worker import simulation_profile

NOW = datetime(2026, 10, 16, tzinfo=timezone.utc)
REQUEST = ShippingQuoteRequest('ES', '01001', 'ES', '28001', 1200, Dimensions(200, 150, 100))
PAYLOAD = dict(origin_country_code='ES', origin_postal_code='01001', destination_country_code='ES',
               destination_postal_code='28001', weight_grams=1200,
               dimensions=dict(width_mm=200, height_mm=150, depth_mm=100))


class QuotationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.repository = AsyncMock(spec=QuotationRepository)
        self.publisher = AsyncMock(spec=QuotationPublisher)
        self.service = QuotationService(self.repository, self.publisher, lambda: NOW)
        self.quotation = Quotation(uuid4(), REQUEST, QuotationStatus.PENDING, NOW)

    async def test_submit_saves_before_one_confirmed_publication(self):
        events = []
        async def save(item):
            events.append(('save', item.id))
        async def publish(identifier):
            self.assertEqual(events, [('save', identifier)])
            events.append(('publish', identifier))
        self.repository.save.side_effect = save
        self.publisher.publish.side_effect = publish
        item = await self.service.submit(REQUEST)
        self.assertEqual(events, [('save', item.id), ('publish', item.id)])
        self.assertEqual(item.status, QuotationStatus.PENDING)
        self.assertEqual(item.request.origin_postal_code, '01001')
        self.repository.fail.assert_not_awaited()

    async def test_failed_save_never_publishes(self):
        self.repository.save.side_effect = QuotationStorageError()
        with self.assertRaises(QuotationStorageError):
            await self.service.submit(REQUEST)
        self.publisher.publish.assert_not_awaited()

    async def test_publication_failure_has_saved_id_and_no_retry(self):
        self.publisher.publish.side_effect = PublicationError()
        for storage_failure in (False, True):
            self.repository.reset_mock()
            self.publisher.reset_mock()
            self.repository.fail.side_effect = QuotationStorageError() if storage_failure else None
            with self.assertRaises(SubmissionError) as raised:
                await self.service.submit(REQUEST)
            identifier = raised.exception.quotation_id
            self.publisher.publish.assert_awaited_once_with(identifier)
            self.repository.fail.assert_awaited_once_with(identifier, QuotationStatus.PENDING,
                ProcessErrorCode.PUBLISH_ERROR, NOW)

    async def test_process_compares_once_and_completes_even_all_failed(self):
        comparator = AsyncMock(spec=ShippingQuoteService)
        results = (ProviderResult('a', ProviderStatus.FAILED, error_code=ProviderErrorCode.PROVIDER_TIMEOUT),)
        comparator.compare.return_value = results
        self.repository.start.return_value = replace(self.quotation, status=QuotationStatus.PROCESSING)
        processor = QuotationProcessor(self.repository, comparator, lambda: NOW)
        await processor.process(self.quotation.id)
        comparator.compare.assert_awaited_once_with(REQUEST)
        self.repository.complete.assert_awaited_once_with(self.quotation.id, results, NOW)
        self.repository.fail.assert_not_awaited()

    async def test_not_pending_is_ignored_and_unexpected_failure_is_not_retried(self):
        comparator = AsyncMock(spec=ShippingQuoteService)
        processor = QuotationProcessor(self.repository, comparator, lambda: NOW)
        self.repository.start.return_value = None
        await processor.process(self.quotation.id)
        comparator.compare.assert_not_awaited()
        self.repository.start.return_value = self.quotation
        comparator.compare.side_effect = RuntimeError('Unexpected')
        await processor.process(self.quotation.id)
        comparator.compare.assert_awaited_once()
        self.repository.fail.assert_awaited_once_with(self.quotation.id, QuotationStatus.PROCESSING,
            ProcessErrorCode.PROCESSING_ERROR, NOW)

    async def test_ack_before_any_processing_and_ack_failure_stops_execution(self):
        message = AsyncMock()
        message.body = json.dumps({'quotation_id': str(self.quotation.id)}).encode()
        processor = AsyncMock(spec=QuotationProcessor)
        async def process(identifier):
            message.ack.assert_awaited_once_with()
            self.assertEqual(identifier, self.quotation.id)
        processor.process.side_effect = process
        await handle_delivery(message, processor)
        processor.process.assert_awaited_once()
        processor.reset_mock()
        message.ack.side_effect = ConnectionError()
        with self.assertRaises(ConnectionError):
            await handle_delivery(message, processor)
        processor.process.assert_not_awaited()

    async def test_invalid_messages_are_acknowledged_and_ignored(self):
        for body in (b'bad', b'[]', b'{}', b'{"quotation_id": false}', b'{"quotation_id":"bad"}',
                     json.dumps({'quotation_id': str(uuid4()), 'extra': 1}).encode()):
            message = AsyncMock(body=body)
            processor = AsyncMock(spec=QuotationProcessor)
            await handle_delivery(message, processor)
            message.ack.assert_awaited_once()
            processor.process.assert_not_awaited()

    async def test_excessively_nested_json_is_acknowledged_and_ignored(self):
        message = AsyncMock(body=b'[' * 10000 + b']' * 10000)
        processor = AsyncMock(spec=QuotationProcessor)
        await handle_delivery(message, processor)
        message.ack.assert_awaited_once_with()
        processor.process.assert_not_awaited()

    async def test_http_validation_read_errors_and_publication_error(self):
        app = FastAPI()
        app.include_router(create_quotation_router(self.service))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url='http://test') as client:
            for invalid in ({**PAYLOAD, 'extra': 1}, {**PAYLOAD, 'weight_grams': True},
                            {**PAYLOAD, 'origin_country_code': 'FR'}, {**PAYLOAD, 'origin_postal_code': 1001},
                            {**PAYLOAD, 'dimensions': {'width_mm': 0, 'height_mm': 1, 'depth_mm': 1}}):
                self.assertEqual((await client.post('/quotations', json=invalid)).status_code, 422)
            self.repository.save.assert_not_awaited()
            response = await client.post('/quotations', json=PAYLOAD)
            self.assertEqual(response.status_code, 202)
            self.assertEqual(response.headers['location'], '/quotations/' + response.json()['id'])
            self.repository.get.return_value = self.quotation
            response = await client.get('/quotations/' + str(self.quotation.id))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['request']['origin_postal_code'], '01001')
            self.assertEqual(response.json()['results'], [])
            self.assertTrue(response.json()['created_at'].endswith('Z'))
            self.repository.get.return_value = None
            self.assertEqual((await client.get('/quotations/' + str(uuid4()))).status_code, 404)
            self.assertEqual((await client.get('/quotations/bad')).status_code, 422)
            self.repository.get.side_effect = QuotationStorageError('secret')
            response = await client.get('/quotations/' + str(uuid4()))
            self.assertEqual(response.status_code, 503)
            self.assertNotIn('secret', response.text)
            self.publisher.publish.side_effect = PublicationError()
            response = await client.post('/quotations', json=PAYLOAD)
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()['detail']['code'], 'PUBLISH_ERROR')
            self.assertIn('id', response.json()['detail'])
            self.repository.save.side_effect = QuotationStorageError('secret')
            self.assertEqual((await client.post('/quotations', json=PAYLOAD)).status_code, 503)

    async def test_response_waits_for_confirmation(self):
        confirmed = asyncio.Event()
        self.publisher.publish.side_effect = lambda identifier: None
        async def publish(identifier):
            await confirmed.wait()
        self.publisher.publish.side_effect = publish
        task = asyncio.create_task(self.service.submit(REQUEST))
        await asyncio.sleep(0)
        self.assertFalse(task.done())
        confirmed.set()
        await task

    async def test_broker_cleanup_when_open_fails_and_publish_requires_confirmation(self):
        from unittest.mock import patch
        connection = AsyncMock()
        connection.is_closed = False
        channel = AsyncMock()
        channel.is_closed = False
        connection.channel.return_value = channel
        channel.declare_queue.side_effect = RuntimeError('setup')
        broker = RabbitMQ('amqp://unused')
        with patch('adapters.queue.rabbitmq.aio_pika.connect', return_value=connection):
            with self.assertRaises(RuntimeError):
                await broker.open()
        channel.close.assert_awaited_once()
        connection.close.assert_awaited_once()
        channel.default_exchange.publish.return_value = None
        with self.assertRaises(PublicationError):
            await broker.publish(uuid4())

    def test_worker_profile_defaults_overrides_and_validation(self):
        from unittest.mock import patch
        with patch.dict('os.environ', {}, clear=True):
            profile = simulation_profile()
        self.assertEqual((profile.delay_min_seconds, profile.delay_max_seconds,
            profile.no_response_probability, profile.error_probability), (.05, .5, .05, .10))
        values = {name: '0' for name in ('SHIPPING_DELAY_MIN_SECONDS', 'SHIPPING_DELAY_MAX_SECONDS',
            'SHIPPING_NO_RESPONSE_PROBABILITY', 'SHIPPING_ERROR_PROBABILITY')}
        with patch.dict('os.environ', values, clear=True):
            self.assertEqual(simulation_profile().error_probability, 0)
        for value in ('nan', '-1', 'bad'):
            with patch.dict('os.environ', {'SHIPPING_ERROR_PROBABILITY': value}, clear=True):
                with self.assertRaises(ValueError):
                    simulation_profile()

    async def test_worker_shutdown_cancels_provider_work_and_closes_resources(self):
        from unittest.mock import patch
        from worker import run_worker
        from domain.shipping_quotes import QuoteOffers
        entered, cancelled = asyncio.Event(), asyncio.Event()
        class WaitingProvider:
            code = 'waiting'
            async def quote(self, request: ShippingQuoteRequest) -> QuoteOffers:
                entered.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    cancelled.set()
                raise AssertionError('unreachable')
        engine, broker = AsyncMock(), AsyncMock()
        repository = AsyncMock(spec=QuotationRepository)
        repository.start.return_value = self.quotation
        async def consume(processor):
            await processor.process(self.quotation.id)
        broker.consume.side_effect = consume
        with patch('worker.create_database', return_value=(engine, object())), \
             patch('worker.RabbitMQ', return_value=broker), \
             patch('worker.SqlModelQuotationRepository', return_value=repository), \
             patch('worker.ShippingQuoteService', return_value=ShippingQuoteService([WaitingProvider()])):
            task = asyncio.create_task(run_worker())
            await entered.wait()
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
        self.assertTrue(cancelled.is_set())
        broker.close.assert_awaited_once()
        engine.dispose.assert_awaited_once()
        repository.fail.assert_not_awaited()
        repository.complete.assert_not_awaited()

    async def test_worker_startup_failure_closes_broker_and_database(self):
        from unittest.mock import patch
        from worker import run_worker
        engine, broker = AsyncMock(), AsyncMock()
        broker.open.side_effect = ConnectionError('unavailable')
        with patch('worker.create_database', return_value=(engine, object())), \
             patch('worker.RabbitMQ', return_value=broker):
            with self.assertRaises(ConnectionError):
                await run_worker()
        broker.close.assert_awaited_once()
        engine.dispose.assert_awaited_once()

    async def test_publisher_uses_one_persistent_mandatory_confirmed_message(self):
        from unittest.mock import patch
        from pamqp.commands import Basic
        import aio_pika
        connection, channel = AsyncMock(), AsyncMock()
        channel.is_closed = connection.is_closed = False
        connection.channel.return_value = channel
        channel.default_exchange.publish.return_value = Basic.Ack()
        broker = RabbitMQ('amqp://unused')
        with patch('adapters.queue.rabbitmq.aio_pika.connect', return_value=connection):
            await broker.open()
        identifier = uuid4()
        await broker.publish(identifier)
        connection.channel.assert_awaited_once_with(publisher_confirms=True, on_return_raises=True)
        channel.set_qos.assert_awaited_once_with(prefetch_count=1)
        channel.declare_queue.assert_awaited_once_with('shipping.quotations', durable=True)
        channel.default_exchange.publish.assert_awaited_once()
        call = channel.default_exchange.publish.call_args
        message = call.args[0]
        self.assertEqual(json.loads(message.body), {'quotation_id': str(identifier)})
        self.assertEqual(message.delivery_mode, aio_pika.DeliveryMode.PERSISTENT)
        self.assertEqual(call.kwargs, dict(routing_key='shipping.quotations', mandatory=True, timeout=5))
