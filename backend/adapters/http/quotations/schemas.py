from datetime import datetime
from typing import Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, model_validator
from application.quotation_models import QuotationStatus, ProcessErrorCode
from application.shipping_quotes import ProviderStatus, ProviderErrorCode
from domain.lockers import Dimensions
from domain.shipping_quotes import ShippingQuoteRequest


class ShippingDimensions(BaseModel):
    model_config = ConfigDict(extra='forbid', from_attributes=True)
    width_mm: StrictInt = Field(ge=1, le=2000)
    height_mm: StrictInt = Field(ge=1, le=2000)
    depth_mm: StrictInt = Field(ge=1, le=2000)


class QuotationInput(BaseModel):
    model_config = ConfigDict(extra='forbid', from_attributes=True)
    origin_country_code: StrictStr
    origin_postal_code: StrictStr
    destination_country_code: StrictStr
    destination_postal_code: StrictStr
    weight_grams: StrictInt = Field(ge=1, le=30000)
    dimensions: ShippingDimensions

    def domain(self) -> ShippingQuoteRequest:
        return ShippingQuoteRequest(self.origin_country_code, self.origin_postal_code,
            self.destination_country_code, self.destination_postal_code, self.weight_grams,
            Dimensions(self.dimensions.width_mm, self.dimensions.height_mm, self.dimensions.depth_mm))

    @model_validator(mode='after')
    def valid(self) -> Self:
        self.domain()
        return self


class QuotationAccepted(BaseModel):
    id: UUID
    status: QuotationStatus


class OfferResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    service_code: str
    price_cents: int
    currency: str
    transit_days_min: int
    transit_days_max: int


class ProviderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    provider_code: str
    status: ProviderStatus
    offers: list[OfferResponse]
    error_code: ProviderErrorCode | None


class QuotationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    request: QuotationInput
    status: QuotationStatus
    created_at: datetime
    finished_at: datetime | None
    process_error_code: ProcessErrorCode | None
    results: list[ProviderResponse]
