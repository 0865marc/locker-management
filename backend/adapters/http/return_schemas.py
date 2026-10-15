from datetime import datetime
from uuid import UUID

from pydantic import ConfigDict, StrictStr
from adapters.http.locker_schemas import ReceptionInput, AssignmentResponse
from domain.returns import ReturnStatus


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
