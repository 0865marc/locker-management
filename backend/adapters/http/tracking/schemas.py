from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from adapters.http.lockers.schemas import AddressInput, CoordinatesInput
from domain.deliveries import DeliveryStatus
from domain.returns import ReturnStatus


class TrackingLockerResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    location_id: str | None
    address: AddressInput | None
    coordinates: CoordinatesInput | None


class TrackingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    kind: Literal["delivery", "return"]
    status: DeliveryStatus | ReturnStatus
    locker_relation: Literal["current", "last_known", "unassigned"]
    locker_id: UUID | None
    locker: TrackingLockerResponse | None
