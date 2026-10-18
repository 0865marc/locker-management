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
from domain.lockers import Dimensions
from domain.returns import Return, ReturnStatus

COLUMNS = (
    "id",
    "tracking_number",
    "carrier_code",
    "sender_name",
    "received_at",
    "status",
    "handed_over_at",
)


def values(item: Return) -> tuple[D1Value, ...]:
    return (
        str(item.id),
        item.tracking_number,
        item.carrier_code,
        item.sender_name,
        timestamp(item.received_at),
        item.status.value,
        optional_timestamp(item.handed_over_at),
    )


def parcel_return(row: D1Row) -> Return:
    locker_id, cell_id, dimensions = assignment(row)
    return Return(
        id=identifier(row, "id"),
        tracking_number=text(row, "tracking_number"),
        carrier_code=text(row, "carrier_code"),
        sender_name=optional_text(row, "sender_name"),
        received_at=instant(row, "received_at"),
        status=ReturnStatus(text(row, "status")),
        handed_over_at=optional_instant(row, "handed_over_at"),
        locker_id=locker_id,
        compartment_id=cell_id,
        parcel_dimensions=dimensions,
    )


class D1ReturnRepository:
    def __init__(self, provider: D1Provider) -> None:
        self.store = CustodyStore(
            provider, "returns", COLUMNS, ReturnStatus.AWAITING_CARRIER.value
        )

    async def save(self, item: Return) -> None:
        if item.locker_id is not None:
            raise ValueError("Use receive_in_locker for assigned receptions")
        await self.store.save(values(item))

    async def receive_in_locker(
        self, item: Return, locker_id: UUID, dimensions: Dimensions
    ) -> Return:
        if item.locker_id is not None:
            raise ValueError("Reception requires an unassigned entity")
        if item.status != ReturnStatus.AWAITING_CARRIER:
            raise ValueError("Reception requires pending custody")
        cell_id = await self.store.receive(
            item.id, values(item), locker_id, dimensions, timestamp(item.received_at)
        )
        return replace(
            item,
            locker_id=locker_id,
            compartment_id=cell_id,
            parcel_dimensions=dimensions,
        )

    async def list_all(self) -> list[Return]:
        return [parcel_return(row) for row in await self.store.read()]

    async def get_by_id(self, identifier: UUID) -> Return | None:
        rows = await self.store.read(identifier)
        return parcel_return(rows[0]) if rows else None

    async def save_exit(self, item: Return) -> bool:
        if item.status == ReturnStatus.AWAITING_CARRIER:
            raise ValueError("A custody exit requires a terminal return")
        if item.handed_over_at is None:
            raise ValueError("A custody exit requires a timestamp")
        return await self.store.exit(
            item.id,
            ("status", "handed_over_at"),
            (item.status.value, timestamp(item.handed_over_at)),
            timestamp(item.handed_over_at),
        )
