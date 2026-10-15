from datetime import datetime
from uuid import UUID
from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, StrictStr, field_validator, model_validator

from adapters.http.locker_schemas import DimensionsInput

from domain.models import DeliveryStatus, ReturnStatus


class ReceptionInput(BaseModel):
    locker_id: UUID | None = None
    parcel_dimensions: DimensionsInput | None = None
    @model_validator(mode="after")
    def paired(self) -> Self:
        if (self.locker_id is None) != (self.parcel_dimensions is None):
            raise ValueError("locker_id y parcel_dimensions deben indicarse juntos")
        return self

class CreateDelivery(ReceptionInput):
    model_config = ConfigDict(extra="forbid")

    tracking_number: StrictStr
    carrier_code: StrictStr
    recipient_name: StrictStr
    recipient_phone: StrictStr | None = None
    pickup_deadline_at: AwareDatetime | None = None

    @field_validator("pickup_deadline_at", mode="before")
    @classmethod
    def deadline_is_datetime_text(cls, value: object) -> datetime | None:
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError as error:
                raise ValueError("pickup_deadline_at debe ser una fecha con zona horaria") from error
        if value is not None and not isinstance(value, datetime):
            raise ValueError("pickup_deadline_at debe ser una fecha con zona horaria")
        return value


class AssignmentResponse(BaseModel):
    locker_id: UUID | None
    compartment_id: UUID | None
    parcel_dimensions: DimensionsInput | None

class DeliveryResponse(AssignmentResponse):
    id: UUID
    tracking_number: str
    carrier_code: str
    recipient_name: str
    recipient_phone: str | None
    pickup_deadline_at: datetime | None
    received_at: datetime
    status: DeliveryStatus
    collected_at: datetime | None
    returned_to_carrier_at: datetime | None


class CreateReturn(ReceptionInput):
    model_config = ConfigDict(extra="forbid")

    tracking_number: StrictStr
    carrier_code: StrictStr
    sender_name: StrictStr | None = None


class ReturnResponse(AssignmentResponse):
    id: UUID
    tracking_number: str
    carrier_code: str
    sender_name: str | None
    received_at: datetime
    status: ReturnStatus
    handed_over_at: datetime | None
