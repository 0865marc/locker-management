from datetime import datetime
from typing import Protocol
from uuid import UUID

from application.quotations.models import (
    ProcessErrorCode,
    ProviderResult,
    Quotation,
    QuotationStatus,
)
from domain.shipping_quotes import NoCoverage, QuoteOffers, ShippingQuoteRequest


class QuotationRepository(Protocol):
    async def save(self, quotation: Quotation) -> None: ...
    async def get(self, quotation_id: UUID) -> Quotation | None: ...
    async def start(self, quotation_id: UUID) -> Quotation | None: ...
    async def complete(
        self,
        quotation_id: UUID,
        results: tuple[ProviderResult, ...],
        finished_at: datetime,
    ) -> None: ...
    async def fail(
        self,
        quotation_id: UUID,
        expected: QuotationStatus,
        error: ProcessErrorCode,
        finished_at: datetime,
    ) -> None: ...


class QuotationPublisher(Protocol):
    async def publish(self, quotation_id: UUID) -> None: ...


class ShippingProvider(Protocol):
    @property
    def code(self) -> str: ...

    async def quote(
        self, request: ShippingQuoteRequest
    ) -> QuoteOffers | NoCoverage: ...
