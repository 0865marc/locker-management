"""Browser-only infrastructure: real composition/routes/CORS, fake persistence.

No fixtures are imported into the production frontend or written to a database.
"""

import os
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch
from uuid import UUID

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
os.environ["CORS_ALLOWED_ORIGINS"] = "http://127.0.0.1:4321"

from application.deliveries.ports import DeliveryRepository
from application.lockers.ports import LockerRepository
from application.quotations.models import (
    ProviderErrorCode,
    ProviderResult,
    ProviderStatus,
    Quotation,
    QuotationStatus,
)
from application.quotations.ports import QuotationRepository
from application.returns.ports import ReturnRepository
from domain.deliveries import Delivery
from domain.lockers import Address, Compartment, Coordinates, Dimensions, Locker
from domain.returns import Return
from domain.shipping_quotes import ShippingOffer
from main import create_app

locker_id = UUID("00000000-0000-4000-8000-000000000001")
locker = Locker(
    id=locker_id,
    location_id="Locker CORS",
    address=Address("ES", "01001", "Madrid", "Madrid", "Calle de prueba", "1"),
    coordinates=Coordinates(40.4168, -3.7038),
    compartments=(Compartment(locker_id, Dimensions(400, 400, 600)),),
)
repository = AsyncMock(spec=LockerRepository)
tracking_locker_id = UUID("00000000-0000-4000-8000-000000000002")
tracking_locker = Locker(
    id=tracking_locker_id,
    location_id="Locker de seguimiento",
    active=False,
    address=Address("ES", "28001", "Madrid", "Madrid", "Calle de seguimiento", "2"),
    coordinates=Coordinates(40.418, -3.706),
    compartments=(
        Compartment(tracking_locker_id, Dimensions(400, 400, 600), occupied=True),
    ),
)
repository.list_all.return_value = [locker, tracking_locker]
repository.get_by_id.side_effect = {
    locker_id: locker,
    tracking_locker_id: tracking_locker,
}.get

now = datetime.now(timezone.utc)


def parcel_id(index: int) -> UUID:
    return UUID(f"00000000-0000-4000-8000-{index:012d}")


delivery_current = Delivery(
    "TRACKING-FIXTURE",
    "fixture",
    "No se expone",
    now,
    id=parcel_id(1001),
    locker_id=tracking_locker_id,
    compartment_id=parcel_id(2001),
    parcel_dimensions=Dimensions(100, 100, 100),
)
return_current = Return(
    "RETURN-FIXTURE",
    "fixture",
    now,
    id=parcel_id(1002),
    locker_id=tracking_locker_id,
    compartment_id=parcel_id(2002),
    parcel_dimensions=Dimensions(100, 100, 100),
)
delivery_records = {
    parcel_id(1001): delivery_current,
    parcel_id(1003): Delivery(
        "UNASSIGNED", "fixture", "No se expone", now, id=parcel_id(1003)
    ),
    parcel_id(1004): Delivery(
        "AMBIGUOUS", "fixture", "No se expone", now, id=parcel_id(1004)
    ),
    parcel_id(1006): replace(delivery_current.collect(now), id=parcel_id(1006)),
    parcel_id(1007): replace(
        delivery_current.return_to_carrier(now), id=parcel_id(1007)
    ),
}
return_records = {
    parcel_id(1002): return_current.hand_over(now),
    parcel_id(1004): Return("AMBIGUOUS", "fixture", now, id=parcel_id(1004)),
    parcel_id(1005): replace(
        return_current, id=parcel_id(1005), locker_id=parcel_id(999)
    ),
    parcel_id(1008): replace(return_current, id=parcel_id(1008)),
}
delivery_repository = AsyncMock(spec=DeliveryRepository)
delivery_repository.get_by_id.side_effect = delivery_records.get
return_repository = AsyncMock(spec=ReturnRepository)
return_repository.get_by_id.side_effect = return_records.get

quotations: dict[UUID, Quotation] = {}
reads: dict[UUID, int] = {}


async def save(quotation: Quotation) -> None:
    quotations[quotation.id] = quotation
    reads[quotation.id] = 0


async def get(quotation_id: UUID) -> Quotation | None:
    quotation = quotations.get(quotation_id)
    if quotation is None:
        return None
    reads[quotation_id] += 1
    if reads[quotation_id] == 1:
        return quotation
    return replace(
        quotation,
        status=QuotationStatus.COMPLETED,
        finished_at=datetime.now(timezone.utc),
        results=(
            ProviderResult(
                "sim-economy",
                ProviderStatus.QUOTED,
                (ShippingOffer("standard", 1234, "EUR", 2, 4),),
            ),
            ProviderResult("sim-standard", ProviderStatus.NOT_COVERED),
            ProviderResult(
                "sim-express",
                ProviderStatus.FAILED,
                error_code=ProviderErrorCode.PROVIDER_TIMEOUT,
            ),
        ),
    )


quotation_repository = AsyncMock(spec=QuotationRepository)
quotation_repository.save.side_effect = save
quotation_repository.get.side_effect = get
with (
    patch("main.create_database", return_value=(AsyncMock(), object())),
    patch("main.SqlModelLockerRepository", return_value=repository),
    patch("main.SqlModelDeliveryRepository", return_value=delivery_repository),
    patch("main.SqlModelReturnRepository", return_value=return_repository),
    patch("main.SqlModelQuotationRepository", return_value=quotation_repository),
):
    app = create_app("postgresql+asyncpg://unused/unused", publisher=AsyncMock())

uvicorn.run(app, host="127.0.0.1", port=8765)
