from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from domain.deliveries import DeliveryStatus
from domain.lockers import Address, Coordinates
from domain.returns import ReturnStatus


@dataclass(frozen=True)
class TrackingLocker:
    location_id: str | None
    address: Address | None
    coordinates: Coordinates | None


@dataclass(frozen=True)
class TrackedParcel:
    id: UUID
    kind: Literal["delivery", "return"]
    status: DeliveryStatus | ReturnStatus
    locker_relation: Literal["current", "last_known", "unassigned"]
    locker_id: UUID | None
    locker: TrackingLocker | None
