from typing import Literal
from uuid import UUID

from application.deliveries.ports import DeliveryRepository
from application.lockers.ports import LockerRepository
from application.returns.ports import ReturnRepository
from application.tracking.models import TrackedParcel, TrackingLocker
from domain.deliveries import Delivery, DeliveryStatus
from domain.returns import Return, ReturnStatus


class TrackingNotFoundError(LookupError):
    pass


class TrackingConflictError(ValueError):
    pass


class TrackingService:
    def __init__(
        self,
        deliveries: DeliveryRepository,
        returns: ReturnRepository,
        lockers: LockerRepository,
    ) -> None:
        self.deliveries = deliveries
        self.returns = returns
        self.lockers = lockers

    async def get_by_id(self, identifier: UUID) -> TrackedParcel:
        delivery = await self.deliveries.get_by_id(identifier)
        returned = await self.returns.get_by_id(identifier)
        if delivery is not None and returned is not None:
            raise TrackingConflictError("Parcel UUID identifies multiple flows")
        parcel: Delivery | Return
        kind: Literal["delivery", "return"]
        if delivery is not None:
            parcel, kind = delivery, "delivery"
        elif returned is not None:
            parcel, kind = returned, "return"
        else:
            raise TrackingNotFoundError("Parcel not found")
        if parcel.locker_id is None:
            return TrackedParcel(
                identifier, kind, parcel.status, "unassigned", None, None
            )
        current = parcel.status in (
            DeliveryStatus.AWAITING_PICKUP,
            ReturnStatus.AWAITING_CARRIER,
        )
        locker = await self.lockers.get_by_id(parcel.locker_id)
        summary = (
            TrackingLocker(locker.location_id, locker.address, locker.coordinates)
            if locker is not None
            else None
        )
        return TrackedParcel(
            identifier,
            kind,
            parcel.status,
            "current" if current else "last_known",
            parcel.locker_id,
            summary,
        )
