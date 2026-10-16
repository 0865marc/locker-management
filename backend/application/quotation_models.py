"""Persistent quotation state, independent of storage and transport."""
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from uuid import UUID

from application.shipping_quotes import ProviderResult
from domain.shipping_quotes import ShippingQuoteRequest


class QuotationStatus(str, Enum):
    PENDING = 'PENDING'
    PROCESSING = 'PROCESSING'
    COMPLETED = 'COMPLETED'
    FAILED = 'FAILED'


class ProcessErrorCode(str, Enum):
    PUBLISH_ERROR = 'PUBLISH_ERROR'
    PROCESSING_ERROR = 'PROCESSING_ERROR'


@dataclass(frozen=True)
class Quotation:
    id: UUID
    request: ShippingQuoteRequest
    status: QuotationStatus
    created_at: datetime
    finished_at: datetime | None = None
    process_error_code: ProcessErrorCode | None = None
    results: tuple[ProviderResult, ...] = ()


class QuotationStorageError(Exception):
    """Storage is unavailable or a transaction failed."""


class PublicationError(Exception):
    """Broker publication was not confirmed."""


class SubmissionError(Exception):
    def __init__(self, quotation_id: UUID) -> None:
        super().__init__('Quotation publication failed')
        self.quotation_id = quotation_id
