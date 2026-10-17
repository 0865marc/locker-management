"""Application quotation adapters against local workerd D1 via the test bridge.

This exercises native D1 SQL, not Python Workers or the Queues service.
"""

import asyncio
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import httpx
from fastapi import FastAPI
from native_d1 import NativeD1

from adapters.database.d1.core import query
from adapters.database.d1.quotations import D1QuotationRepository
from adapters.http.quotations.routes import create_quotation_router
from adapters.queue.cloudflare import CloudflareQuotationPublisher, handle_message
from application.quotations.comparison import ShippingQuoteComparator
from application.quotations.errors import QuotationStorageError, SubmissionError
from application.quotations.models import (
    ProcessErrorCode,
    ProviderErrorCode,
    ProviderResult,
    ProviderStatus,
    Quotation,
    QuotationStatus,
)
from application.quotations.use_cases import QuotationProcessor, QuotationService
from domain.lockers import Dimensions
from domain.shipping_quotes import (
    NoCoverage,
    QuoteOffers,
    ShippingOffer,
    ShippingQuoteRequest,
)

NOW = datetime(2026, 10, 17, 12, 4, 5, 123456, tzinfo=timezone.utc)
REQUEST = ShippingQuoteRequest(
    "ES", "01001", "ES", "28001", 1200, Dimensions(100, 200, 300)
)
RESULTS = (
    ProviderResult("z", ProviderStatus.NOT_COVERED),
    ProviderResult(
        "b", ProviderStatus.FAILED, error_code=ProviderErrorCode.PROVIDER_TIMEOUT
    ),
    ProviderResult(
        "a",
        ProviderStatus.QUOTED,
        (
            ShippingOffer("z", 2147483647, "EUR", 2, 3),
            ShippingOffer("a", 345, "EUR", 1, 2),
        ),
    ),
)


class Provider:
    code = "fixed"

    def __init__(self) -> None:
        self.calls = 0

    async def quote(self, request: ShippingQuoteRequest) -> QuoteOffers | NoCoverage:
        self.calls += 1
        return QuoteOffers((ShippingOffer("standard", 123, "EUR", 1, 2),))


class Queue:
    def __init__(self, fail: bool = False) -> None:
        self.payloads: list[dict[str, str]] = []
        self.fail = fail

    async def send(self, body: dict[str, str]) -> None:
        self.payloads.append(body)
        if self.fail:
            raise OSError("publication unavailable")


class Message:
    def __init__(self, body: object) -> None:
        self.body = body
        self.acked = False

    def ack(self) -> None:
        self.acked = True


class D1QuotationTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self) -> None:
        self.db = await NativeD1().__aenter__()
        self.addAsyncCleanup(self.db.close)
        await self.db.migrate()
        self.repository = D1QuotationRepository(lambda: self.db)
        self.quotation = Quotation(uuid4(), REQUEST, QuotationStatus.PENDING, NOW)
        await self.repository.save(self.quotation)

    async def asyncTearDown(self) -> None:
        await self.db.close()

    async def test_roundtrip_mixed_results_order_precision_and_snapshot(self) -> None:
        self.assertEqual(await self.repository.get(self.quotation.id), self.quotation)
        await self.repository.start(self.quotation.id)
        before = len(self.db.statements)
        await self.repository.complete(
            self.quotation.id, RESULTS, NOW + timedelta(seconds=1)
        )
        self.assertEqual(len(self.db.statements) - before, 3)
        other = D1QuotationRepository(lambda: self.db)
        before = len(self.db.statements)
        result = await other.get(self.quotation.id)
        self.assertEqual(len(self.db.statements) - before, 1)
        assert result is not None
        self.assertEqual(result.status, QuotationStatus.COMPLETED)
        self.assertEqual(result.created_at, NOW)
        self.assertEqual([r.provider_code for r in result.results], ["a", "b", "z"])
        self.assertEqual([o.service_code for o in result.results[0].offers], ["a", "z"])
        self.assertEqual(result.results[0].offers[1].price_cents, 2147483647)
        self.assertTrue(all(len(params) <= 100 for _, params in self.db.statements))

    async def test_duplicate_start_only_one_winner_and_later_states_ignored(
        self,
    ) -> None:
        starts = await asyncio.gather(
            *(self.repository.start(self.quotation.id) for _ in range(4))
        )
        self.assertEqual(sum(result is not None for result in starts), 1)
        await self.repository.complete(self.quotation.id, RESULTS, NOW)
        self.assertIsNone(await self.repository.start(self.quotation.id))
        self.assertIsNone(await self.repository.start(uuid4()))

    async def test_wrong_state_completion_rejects_without_any_writes(self) -> None:
        for identifier in (self.quotation.id, uuid4()):
            with self.assertRaises(QuotationStorageError):
                await self.repository.complete(identifier, RESULTS, NOW)
        self.assertEqual(await self.repository.get(self.quotation.id), self.quotation)
        self.assertEqual(
            await query(self.db, "SELECT * FROM shipping_provider_results"), ()
        )
        await self.repository.start(self.quotation.id)
        await self.repository.complete(self.quotation.id, RESULTS, NOW)
        before = await self.repository.get(self.quotation.id)
        with self.assertRaises(QuotationStorageError):
            await self.repository.complete(
                self.quotation.id, RESULTS, NOW + timedelta(seconds=5)
            )
        self.assertEqual(await self.repository.get(self.quotation.id), before)

    async def test_middle_batch_failure_rolls_back_results_and_state(self) -> None:
        await self.repository.start(self.quotation.id)
        # Force a genuine constraint failure in statement two, after statement one inserted results.
        await self.db.exec("""CREATE TRIGGER reject_offer BEFORE INSERT ON shipping_offers
            BEGIN SELECT RAISE(ABORT, 'injected offer failure'); END;""")
        with self.assertRaises(QuotationStorageError):
            await self.repository.complete(self.quotation.id, RESULTS, NOW)
        current = await self.repository.get(self.quotation.id)
        assert current is not None
        self.assertEqual(current.status, QuotationStatus.PROCESSING)
        self.assertEqual(current.results, ())
        self.assertEqual(
            await query(self.db, "SELECT * FROM shipping_provider_results"), ()
        )
        self.assertEqual(await query(self.db, "SELECT * FROM shipping_offers"), ())

    async def test_failure_guard_does_not_override_other_state(self) -> None:
        await self.repository.fail(
            self.quotation.id,
            QuotationStatus.PROCESSING,
            ProcessErrorCode.PROCESSING_ERROR,
            NOW,
        )
        self.assertEqual(await self.repository.get(self.quotation.id), self.quotation)
        await self.repository.fail(
            self.quotation.id,
            QuotationStatus.PENDING,
            ProcessErrorCode.PUBLISH_ERROR,
            NOW,
        )
        failed = await self.repository.get(self.quotation.id)
        assert failed is not None
        self.assertEqual(failed.status, QuotationStatus.FAILED)
        self.assertEqual(failed.process_error_code, ProcessErrorCode.PUBLISH_ERROR)
        self.assertIsNone(await self.repository.start(self.quotation.id))
        with self.assertRaises(QuotationStorageError):
            await self.repository.complete(self.quotation.id, RESULTS, NOW)
        self.assertEqual(await self.repository.get(self.quotation.id), failed)

    async def test_queue_flow_real_processor_duplicate_and_publication_failure(
        self,
    ) -> None:
        queue = Queue()
        service = QuotationService(
            self.repository, CloudflareQuotationPublisher(lambda: queue), lambda: NOW
        )
        submitted = await service.submit(REQUEST)
        provider = Provider()
        processor = QuotationProcessor(
            self.repository, ShippingQuoteComparator([provider]), lambda: NOW
        )
        message = Message(queue.payloads[0])
        await handle_message(message, processor)
        self.assertTrue(message.acked)
        await handle_message(Message(queue.payloads[0]), processor)
        self.assertEqual(provider.calls, 1)
        current = await self.repository.get(submitted.id)
        assert current is not None
        self.assertEqual(current.status, QuotationStatus.COMPLETED)
        failing_queue = Queue(fail=True)
        service = QuotationService(
            self.repository,
            CloudflareQuotationPublisher(lambda: failing_queue),
            lambda: NOW,
        )
        with self.assertRaises(SubmissionError) as raised:
            await service.submit(REQUEST)
        failed = await self.repository.get(raised.exception.quotation_id)
        assert failed is not None
        self.assertEqual(failed.process_error_code, ProcessErrorCode.PUBLISH_ERROR)
        self.assertEqual(len(failing_queue.payloads), 1)

    async def test_reads_racing_completion_never_observe_partial_results(self) -> None:
        await self.repository.start(self.quotation.id)
        observed, _ = await asyncio.gather(
            self.repository.get(self.quotation.id),
            self.repository.complete(self.quotation.id, RESULTS, NOW),
        )
        assert observed is not None
        self.assertIn(
            observed.status, (QuotationStatus.PROCESSING, QuotationStatus.COMPLETED)
        )
        self.assertEqual(
            len(observed.results),
            3 if observed.status is QuotationStatus.COMPLETED else 0,
        )

    async def test_http_submission_location_and_publication_error(self) -> None:
        queue = Queue()
        app = FastAPI()
        service = QuotationService(
            self.repository, CloudflareQuotationPublisher(lambda: queue), lambda: NOW
        )
        app.include_router(create_quotation_router(service))
        payload = {
            "origin_country_code": "ES",
            "origin_postal_code": "01001",
            "destination_country_code": "ES",
            "destination_postal_code": "28001",
            "weight_grams": 1200,
            "dimensions": {"width_mm": 100, "height_mm": 200, "depth_mm": 300},
        }
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post("/quotations", json=payload)
            self.assertEqual(response.status_code, 202)
            self.assertEqual(len(queue.payloads), 1)
            identifier = queue.payloads[0]["quotation_id"]
            self.assertEqual(response.headers["location"], f"/quotations/{identifier}")
            self.assertEqual(
                (await client.get(response.headers["location"])).json()["status"],
                "PENDING",
            )
            queue.fail = True
            response = await client.post("/quotations", json=payload)
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["detail"]["code"], "PUBLISH_ERROR")
            failed_id = response.json()["detail"]["id"]
            self.assertEqual(
                (await client.get(f"/quotations/{failed_id}")).json()[
                    "process_error_code"
                ],
                "PUBLISH_ERROR",
            )

    async def test_processing_storage_failure_marks_failed_without_repeating_provider(
        self,
    ) -> None:
        await self.db.exec("""CREATE TRIGGER reject_offer BEFORE INSERT ON shipping_offers
            BEGIN SELECT RAISE(ABORT, 'injected offer failure'); END;""")
        provider = Provider()
        processor = QuotationProcessor(
            self.repository, ShippingQuoteComparator([provider]), lambda: NOW
        )
        await handle_message(
            Message({"quotation_id": str(self.quotation.id)}), processor
        )
        await handle_message(
            Message({"quotation_id": str(self.quotation.id)}), processor
        )
        self.assertEqual(provider.calls, 1)
        failed = await self.repository.get(self.quotation.id)
        assert failed is not None
        self.assertEqual(failed.status, QuotationStatus.FAILED)
        self.assertEqual(failed.process_error_code, ProcessErrorCode.PROCESSING_ERROR)
        self.assertEqual(failed.results, ())
        self.assertEqual(
            await query(self.db, "SELECT * FROM shipping_provider_results"), ()
        )
