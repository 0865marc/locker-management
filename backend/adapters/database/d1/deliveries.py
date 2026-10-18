from dataclasses import replace
from uuid import UUID

from adapters.database.d1.bindings import D1Provider, D1Row, D1Value
from adapters.database.d1.core import (
    identifier,
    instant,
    optional_instant,
    optional_text,
    optional_timestamp,
    text,
    timestamp,
)
from adapters.database.d1.custody import CustodyStore, assignment
from domain.deliveries import Delivery, DeliveryStatus
from domain.lockers import Dimensions

COLUMNS = (
    "id",
    "tracking_number",
    "carrier_code",
    "recipient_name",
    "recipient_phone",
    "received_at",
    "pickup_deadline_at",
    "status",
    "collected_at",
    "returned_to_carrier_at",
)


def values(item: Delivery) -> tuple[D1Value, ...]:
    return (
        str(item.id),
        item.tracking_number,
        item.carrier_code,
        item.recipient_name,
        item.recipient_phone,
        timestamp(item.received_at),
        optional_timestamp(item.pickup_deadline_at),
        item.status.value,
        optional_timestamp(item.collected_at),
        optional_timestamp(item.returned_to_carrier_at),
    )


def delivery(row: D1Row) -> Delivery:
    locker_id, cell_id, dimensions = assignment(row)
    return Delivery(
        id=identifier(row, "id"),
        tracking_number=text(row, "tracking_number"),
        carrier_code=text(row, "carrier_code"),
        recipient_name=text(row, "recipient_name"),
        recipient_phone=optional_text(row, "recipient_phone"),
        received_at=instant(row, "received_at"),
        pickup_deadline_at=optional_instant(row, "pickup_deadline_at"),
        status=DeliveryStatus(text(row, "status")),
        collected_at=optional_instant(row, "collected_at"),
        returned_to_carrier_at=optional_instant(row, "returned_to_carrier_at"),
        locker_id=locker_id,
        compartment_id=cell_id,
        parcel_dimensions=dimensions,
    )


class D1DeliveryRepository:
    def __init__(self, provider: D1Provider) -> None:
        self.store = CustodyStore(
            provider, "deliveries", COLUMNS, DeliveryStatus.AWAITING_PICKUP.value
        )

    async def save(self, delivery: Delivery) -> None:
        if delivery.locker_id is not None:
            raise ValueError("Use receive_in_locker for assigned receptions")
        await self.store.save(values(delivery))

    async def receive_in_locker(
        self, delivery: Delivery, locker_id: UUID, dimensions: Dimensions
    ) -> Delivery:
        if delivery.locker_id is not None:
            raise ValueError("Reception requires an unassigned entity")
        if delivery.status != DeliveryStatus.AWAITING_PICKUP:
            raise ValueError("Reception requires pending custody")
        cell_id = await self.store.receive(
            delivery.id,
            values(delivery),
            locker_id,
            dimensions,
            timestamp(delivery.received_at),
        )
        return replace(
            delivery,
            locker_id=locker_id,
            compartment_id=cell_id,
            parcel_dimensions=dimensions,
        )

    async def list_all(self) -> list[Delivery]:
        return [delivery(row) for row in await self.store.read()]

    async def get_by_id(self, identifier: UUID) -> Delivery | None:
        rows = await self.store.read(identifier)
        return delivery(rows[0]) if rows else None

    async def save_exit(self, delivery: Delivery) -> bool:
        if delivery.status == DeliveryStatus.AWAITING_PICKUP:
            raise ValueError("A custody exit requires a terminal delivery")
        at = delivery.collected_at or delivery.returned_to_carrier_at
        if at is None:
            raise ValueError("A custody exit requires a timestamp")
        return await self.store.exit(
            delivery.id,
            ("status", "collected_at", "returned_to_carrier_at"),
            (
                delivery.status.value,
                optional_timestamp(delivery.collected_at),
                optional_timestamp(delivery.returned_to_carrier_at),
            ),
            timestamp(at),
        )
