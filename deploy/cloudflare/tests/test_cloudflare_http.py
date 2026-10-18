"""Supplemental CPython HTTP/adapters + actual Miniflare D1 integration.

Queue messages below are test objects passed to the real handler. They do not
prove Python Workers execution, native Queues delivery, CPU or Free quotas.
"""

import sys
import unittest
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

import httpx
from native_d1 import NativeD1

from adapters.database.d1.deliveries import D1DeliveryRepository
from adapters.database.d1.lockers import D1LockerRepository
from adapters.database.d1.quotations import D1QuotationRepository
from adapters.database.d1.returns import D1ReturnRepository
from adapters.queue.cloudflare import CloudflareQuotationPublisher, handle_message
from application.quotations.comparison import ShippingQuoteComparator
from application.quotations.errors import ProviderTechnicalError
from application.quotations.use_cases import QuotationProcessor
from composition import create_application, utc_now
from domain.shipping_quotes import (
    NoCoverage,
    QuoteOffers,
    ShippingOffer,
    ShippingQuoteRequest,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts/cloudflare"))
from acceptance import Campaign


class FixtureProvider:
    code = "sim-economy"

    async def quote(self, request: ShippingQuoteRequest) -> QuoteOffers:
        return QuoteOffers((ShippingOffer("standard", 500, "EUR", 1, 2),))


class UncoveredFixtureProvider:
    code = "sim-standard"

    async def quote(self, request: ShippingQuoteRequest) -> NoCoverage:
        return NoCoverage()


class FailedFixtureProvider:
    code = "sim-express"

    async def quote(self, request: ShippingQuoteRequest) -> QuoteOffers:
        raise ProviderTechnicalError("Deterministic fixture failure")


@dataclass
class FixtureQueue:
    messages: list[dict[str, str]] = field(default_factory=list[dict[str, str]])

    async def send(self, body: dict[str, str]) -> None:
        self.messages.append(body)


@dataclass
class FixtureMessage:
    body: object
    acknowledged: bool = False

    def ack(self) -> None:
        self.acknowledged = True


class CloudflareHttpTests(unittest.IsolatedAsyncioTestCase):
    async def test_full_bounded_fixture_and_http_query_budgets(self) -> None:
        async with NativeD1() as database:
            await database.migrate()
            queue = FixtureQueue()
            quotations = D1QuotationRepository(lambda: database)
            publisher = CloudflareQuotationPublisher(lambda: queue)

            def application():
                return create_application(
                    D1DeliveryRepository(lambda: database),
                    D1ReturnRepository(lambda: database),
                    D1LockerRepository(lambda: database),
                    quotations,
                    publisher,
                )

            processor = QuotationProcessor(
                quotations,
                ShippingQuoteComparator(
                    (
                        FixtureProvider(),
                        UncoveredFixtureProvider(),
                        FailedFixtureProvider(),
                    )
                ),
                utc_now,
            )
            measurements: list[tuple[str, str, int, int]] = []
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=application()),
                base_url="http://test",
            ) as client:

                async def request(
                    method: str, path: str, body: object | None = None
                ) -> tuple[int, object]:
                    before = len(database.statements)
                    response = await client.request(method, path, json=body)
                    statements = database.statements[before:]
                    parameters = max(
                        (len(params) for _, params in statements), default=0
                    )
                    measurements.append((method, path, len(statements), parameters))
                    self.assertLessEqual(len(statements), 24, (method, path))
                    self.assertLessEqual(parameters, 100, (method, path))
                    value: object = (
                        response.json()
                        if response.content
                        and "json" in response.headers.get("content-type", "")
                        else None
                    )
                    if response.status_code >= 500:
                        self.fail(
                            f"{method} {path}: {response.status_code} {response.text}"
                        )
                    return response.status_code, value

                async def process_quotes() -> None:
                    self.assertEqual(len(queue.messages), 30)
                    for body in queue.messages:
                        message = FixtureMessage(body)
                        await handle_message(message, processor)
                        self.assertTrue(message.acknowledged)
                        # Duplicate delivery must preserve already committed results.
                        await handle_message(FixtureMessage(body), processor)
                    for body in queue.messages:
                        result = await quotations.get(UUID(body["quotation_id"]))
                        assert result is not None
                        self.assertEqual(len(result.results), 3)

                campaign = Campaign(request, after_quotes=process_quotes)
                result = await campaign.run()
                self.assertLess(len(campaign.samples), 1000)
                self.assertEqual(
                    result["free_acceptance"],
                    "pending platform metrics and quota verification",
                )
            # Separate composition instance uses committed rows from the same D1.
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=application()),
                base_url="http://test",
            ) as second:
                for path, count in (
                    ("/lockers", 10),
                    ("/deliveries", 100),
                    ("/returns", 100),
                ):
                    response = await second.get(path)
                    self.assertEqual(response.status_code, 200, response.text)
                    rows: Sequence[object] = response.json()
                    self.assertEqual(len(rows), count)
            print(
                f"CPython/D1 HTTP campaign: {len(measurements)} requests, "
                f"max {max(count for _, _, count, _ in measurements)} statements, "
                f"max {max(params for _, _, _, params in measurements)} parameters"
            )

            usage = database.usage()
            self.assertLess(usage["rows_written"], 50000)
            print(f"Successful local D1 response metadata (excludes failures): {usage}")
