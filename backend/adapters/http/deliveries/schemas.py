from datetime import datetime
from uuid import UUID

from pydantic import AwareDatetime, field_validator, ConfigDict, StrictStr
from adapters.http.lockers.schemas import ReceptionInput, AssignmentResponse
from domain.deliveries import DeliveryStatus


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
