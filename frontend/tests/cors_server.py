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

from application.lockers.ports import LockerRepository
from application.quotations.models import (
    ProviderErrorCode,
    ProviderResult,
    ProviderStatus,
    Quotation,
    QuotationStatus,
)
from application.quotations.ports import QuotationRepository
from domain.lockers import Address, Compartment, Coordinates, Dimensions, Locker
from domain.shipping_quotes import ShippingOffer
from entrypoints.server.api import create_app

locker_id = UUID("00000000-0000-4000-8000-000000000001")
locker = Locker(
    id=locker_id,
    location_id="Locker CORS",
    address=Address("ES", "01001", "Madrid", "Madrid", "Calle de prueba", "1"),
    coordinates=Coordinates(40.4168, -3.7038),
    compartments=(Compartment(locker_id, Dimensions(400, 400, 600)),),
)
repository = AsyncMock(spec=LockerRepository)
unavailable_locker_id = UUID("00000000-0000-4000-8000-000000000002")
unavailable_locker = Locker(
    id=unavailable_locker_id,
    location_id="Locker no disponible",
    active=False,
    address=Address("ES", "28001", "Madrid", "Madrid", "Calle de prueba", "2"),
    coordinates=Coordinates(40.418, -3.706),
    compartments=(
        Compartment(unavailable_locker_id, Dimensions(400, 400, 600), occupied=True),
    ),
)
repository.list_all.return_value = [locker, unavailable_locker]

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
    patch(
        "entrypoints.server.api.create_database", return_value=(AsyncMock(), object())
    ),
    patch("entrypoints.server.api.SqlModelLockerRepository", return_value=repository),
    patch(
        "entrypoints.server.api.SqlModelQuotationRepository",
        return_value=quotation_repository,
    ),
):
    app = create_app("postgresql+asyncpg://unused/unused", publisher=AsyncMock())

uvicorn.run(app, host="127.0.0.1", port=8765)
