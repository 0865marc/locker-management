"""Committed quotation states, HTTP contracts and atomic batches on PostgreSQL."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from adapters.database.sqlmodel.quotations import SqlModelQuotationRepository
from application.quotations.errors import QuotationStorageError
from application.quotations.models import (
    ProcessErrorCode,
    ProviderErrorCode,
    ProviderResult,
    ProviderStatus,
    Quotation,
    QuotationStatus,
)
from domain.lockers import Dimensions
from domain.shipping_quotes import ShippingOffer, ShippingQuoteRequest
from tests.integration.support import PostgresTestCase

NOW = datetime(2026, 10, 16, tzinfo=timezone.utc)
REQUEST = ShippingQuoteRequest(
    "ES", "01001", "ES", "28001", 1200, Dimensions(200, 150, 100)
)
RESULTS = (
    ProviderResult(
        "a",
        ProviderStatus.QUOTED,
        (
            ShippingOffer("one", 330, "EUR", 3, 3),
            ShippingOffer("two", 400, "EUR", 1, 2),
        ),
    ),
    ProviderResult("b", ProviderStatus.NOT_COVERED),
    ProviderResult(
        "c", ProviderStatus.FAILED, error_code=ProviderErrorCode.PROVIDER_ERROR
    ),
    ProviderResult(
        "d", ProviderStatus.FAILED, error_code=ProviderErrorCode.PROVIDER_TIMEOUT
    ),
)
PAYLOAD = dict(
    origin_country_code="ES",
    origin_postal_code="01001",
    destination_country_code="ES",
    destination_postal_code="28001",
    weight_grams=1200,
    dimensions=dict(width_mm=200, height_mm=150, depth_mm=100),
)


class QuotationPersistenceTests(PostgresTestCase):
    def repository(self):
        return SqlModelQuotationRepository(self.sessions)

    async def new(self):
        quotation = Quotation(uuid4(), REQUEST, QuotationStatus.PENDING, NOW)
        await self.repository().save(quotation)
        return quotation

    async def test_states_batch_results_and_read_from_other_instance(self):
        item = await self.new()
        _, other_sessions = self.database()
        other = SqlModelQuotationRepository(other_sessions)
        self.assertEqual(await other.get(item.id), item)
        started = await self.repository().start(item.id)
        assert started is not None
        self.assertEqual(started.status, QuotationStatus.PROCESSING)
        self.assertEqual(started.results, ())
        self.assertIsNone(await other.start(item.id))
        await self.repository().complete(item.id, RESULTS, NOW)
        loaded = await other.get(item.id)
        assert loaded is not None
        self.assertEqual(loaded.status, QuotationStatus.COMPLETED)
        self.assertEqual(loaded.request, REQUEST)
        self.assertEqual(loaded.results, RESULTS)
        self.assertEqual(loaded.finished_at, NOW)
        self.assertIsNone(loaded.process_error_code)
        await other.fail(
            item.id, QuotationStatus.PENDING, ProcessErrorCode.PUBLISH_ERROR, NOW
        )
        self.assertEqual(await other.get(item.id), loaded)

    async def test_process_errors_are_conditional_and_have_no_provider_results(self):
        for status, error in (
            (QuotationStatus.PENDING, ProcessErrorCode.PUBLISH_ERROR),
            (QuotationStatus.PROCESSING, ProcessErrorCode.PROCESSING_ERROR),
        ):
            item = await self.new()
            if status is QuotationStatus.PROCESSING:
                await self.repository().start(item.id)
            await self.repository().fail(item.id, status, error, NOW)
            loaded = await self.repository().get(item.id)
            assert loaded is not None
            self.assertEqual(
                (
                    loaded.status,
                    loaded.process_error_code,
                    loaded.results,
                    loaded.finished_at,
                ),
                (QuotationStatus.FAILED, error, (), NOW),
            )
            self.assertIsNone(await self.repository().start(item.id))
        self.assertIsNone(await self.repository().get(uuid4()))
        self.assertIsNone(await self.repository().start(uuid4()))

    async def test_failed_batch_rolls_back_every_result_and_final_status(self):
        item = await self.new()
        await self.repository().start(item.id)
        # Duplicate service forces the database insert to fail after result rows flush.
        duplicate = ProviderResult(
            "a", ProviderStatus.QUOTED, (ShippingOffer("one", 330, "EUR", 1, 1),)
        )
        with self.assertRaises(QuotationStorageError):
            await self.repository().complete(item.id, (duplicate, duplicate), NOW)
        loaded = await self.repository().get(item.id)
        assert loaded is not None
        self.assertEqual(loaded.status, QuotationStatus.PROCESSING)
        self.assertEqual(loaded.results, ())
        self.assertIsNone(loaded.finished_at)
        async with self.engine.connect() as connection:
            for table in ("shipping_provider_results", "shipping_offers"):
                self.assertEqual(
                    (
                        await connection.execute(text(f"SELECT count(*) FROM {table}"))
                    ).scalar_one(),
                    0,
                )

    async def test_quote_constraints_and_protected_downgrade(self):
        item = await self.new()
        before = await self.snapshot()
        for state in ("PENDING", "PROCESSING", "COMPLETED", "FAILED"):
            if state == "PROCESSING":
                await self.repository().start(item.id)
            elif state == "COMPLETED":
                await self.repository().complete(item.id, RESULTS, NOW)
            elif state == "FAILED":
                second = await self.new()
                await self.repository().fail(
                    second.id,
                    QuotationStatus.PENDING,
                    ProcessErrorCode.PUBLISH_ERROR,
                    NOW,
                )
            snapshot = await self.snapshot()
            with self.assertRaisesRegex(RuntimeError, "preserve quotation data"):
                await self.migrate("downgrade", "0004")
            self.assertEqual(await self.snapshot(), snapshot)
        for statement, params in (
            (
                "UPDATE shipping_quotations SET status='FAILED',finished_at=:now,process_error_code=NULL WHERE id=:id",
                {"now": NOW, "id": item.id},
            ),
            (
                "INSERT INTO shipping_provider_results VALUES(:id,'bad','FAILED',NULL)",
                {"id": item.id},
            ),
            (
                "INSERT INTO shipping_provider_results VALUES(:id,'unknown','NOT_COVERED',NULL)",
                {"id": uuid4()},
            ),
            (
                "INSERT INTO shipping_provider_results VALUES(:id,'a','NOT_COVERED',NULL)",
                {"id": item.id},
            ),
            (
                "INSERT INTO shipping_offers VALUES(:id,'a','one',330,'EUR',1,1)",
                {"id": item.id},
            ),
            (
                "INSERT INTO shipping_offers VALUES(:id,'missing','new',330,'EUR',1,1)",
                {"id": item.id},
            ),
        ):
            snapshot = await self.snapshot()
            with self.assertRaises(IntegrityError):
                async with self.engine.begin() as connection:
                    await connection.execute(text(statement), params)
            self.assertEqual(await self.snapshot(), snapshot)
        self.assertIn("shipping_quotations", before[0])

    async def test_http_new_instance_reads_pending_completed_and_failed(self):
        app, client, _ = await self.application()
        accepted = await client.post("/quotations", json=PAYLOAD)
        self.assertEqual(accepted.status_code, 202)
        identifier = accepted.json()["id"]
        publisher = app.state.quotation_service.publisher
        publisher.publish.assert_awaited_once()
        await self.close_application(client)
        _, second, _ = await self.application()
        response = await second.get("/quotations/" + identifier)
        self.assertEqual(response.json()["request"]["origin_postal_code"], "01001")
        from uuid import UUID

        await self.repository().start(UUID(identifier))
        await self.repository().complete(
            UUID(identifier), RESULTS, NOW.replace(year=2027)
        )
        response = await second.get("/quotations/" + identifier)
        self.assertEqual(response.json()["status"], "COMPLETED")
        self.assertEqual(len(response.json()["results"]), 4)
        failed = await self.new()
        await self.repository().fail(
            failed.id, QuotationStatus.PENDING, ProcessErrorCode.PUBLISH_ERROR, NOW
        )
        response = await second.get("/quotations/" + str(failed.id))
        self.assertEqual(response.json()["process_error_code"], "PUBLISH_ERROR")
        self.assertEqual(response.json()["results"], [])

    async def test_unavailable_database_returns_503_without_publication(self):
        from main import create_app

        # Port 1 is deliberately unavailable; no credentials appear in HTTP responses.
        publisher = AsyncMock()
        app = create_app(
            "postgresql+asyncpg://unused:private@127.0.0.1:1/unused",
            publisher=publisher,
        )
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app), base_url="http://test"
            ) as client:
                for path in ("/quotations/" + str(uuid4()), "/quotations"):
                    response = (
                        await client.post(path, json=PAYLOAD)
                        if path == "/quotations"
                        else await client.get(path)
                    )
                    self.assertEqual(response.status_code, 503)
                    self.assertNotIn("private", response.text)
        publisher.publish.assert_not_awaited()
