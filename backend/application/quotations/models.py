"""Quotation process and provider results, independent of their executors."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

from domain.lockers import require_instance
from domain.shipping_quotes import (
    QuoteOffers,
    ShippingOffer,
    ShippingQuoteRequest,
    validate_code,
)


def _require_offers_tuple(value: object) -> None:
    if not isinstance(value, tuple):
        raise ValueError("offers must be an immutable tuple")


class ProviderStatus(str, Enum):
    QUOTED = "QUOTED"
    NOT_COVERED = "NOT_COVERED"
    FAILED = "FAILED"


class ProviderErrorCode(str, Enum):
    PROVIDER_ERROR = "PROVIDER_ERROR"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"


@dataclass(frozen=True)
class ProviderResult:
    provider_code: str
    status: ProviderStatus
    offers: tuple[ShippingOffer, ...] = ()
    error_code: ProviderErrorCode | None = None

    def __post_init__(self) -> None:
        validate_code(self.provider_code, "provider_code")
        _require_offers_tuple(self.offers)
        if self.offers:
            QuoteOffers(self.offers)
        require_instance(self.status, ProviderStatus, "Invalid provider status")
        if self.status is ProviderStatus.QUOTED:
            if not self.offers or self.error_code is not None:
                raise ValueError("QUOTED requires offers and no error")
        elif self.status is ProviderStatus.NOT_COVERED:
            if self.offers or self.error_code is not None:
                raise ValueError("NOT_COVERED requires no offers and no error")
        elif self.offers or not isinstance(self.error_code, ProviderErrorCode):
            raise ValueError("FAILED requires no offers and a provider error code")


class QuotationStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ProcessErrorCode(str, Enum):
    PUBLISH_ERROR = "PUBLISH_ERROR"
    PROCESSING_ERROR = "PROCESSING_ERROR"


@dataclass(frozen=True)
class Quotation:
    id: UUID
    request: ShippingQuoteRequest
    status: QuotationStatus
    created_at: datetime
    finished_at: datetime | None = None
    process_error_code: ProcessErrorCode | None = None
    results: tuple[ProviderResult, ...] = ()
