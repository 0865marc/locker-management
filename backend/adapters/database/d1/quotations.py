"""Atomic quotation state transitions over native D1 statements and batches."""

import json
from datetime import datetime
from uuid import UUID

from adapters.database.d1.bindings import D1BindingError, D1Provider, D1Row
from adapters.database.d1.core import (
    batch,
    execute,
    identifier,
    instant,
    integer,
    optional_instant,
    optional_text,
    query,
    statement,
    text,
    timestamp,
)
from application.persistence import PersistenceError
from application.quotations.errors import QuotationStorageError
from application.quotations.models import (
    ProcessErrorCode,
    ProviderErrorCode,
    ProviderResult,
    ProviderStatus,
    Quotation,
    QuotationStatus,
)
from domain.lockers import Dimensions
from domain.shipping_quotes import ShippingOffer, ShippingQuoteRequest

_JOINED = """
SELECT q.*, r.provider_code, r.status AS provider_status, r.error_code,
       o.service_code, CAST(o.price_cents AS TEXT) AS price_cents,
       o.currency, CAST(o.transit_days_min AS TEXT) AS transit_days_min,
       CAST(o.transit_days_max AS TEXT) AS transit_days_max
FROM shipping_quotations q
LEFT JOIN shipping_provider_results r ON r.quotation_id=q.id AND q.status='COMPLETED'
LEFT JOIN shipping_offers o ON o.quotation_id=r.quotation_id AND o.provider_code=r.provider_code
WHERE q.id=? ORDER BY r.provider_code, o.service_code
"""
_GUARD = "EXISTS (SELECT 1 FROM shipping_quotations WHERE id=? AND status='PROCESSING')"


def _quotation(row: D1Row, results: tuple[ProviderResult, ...] = ()) -> Quotation:
    error = optional_text(row, "process_error_code")
    return Quotation(
        identifier(row, "id"),
        ShippingQuoteRequest(
            text(row, "origin_country_code"),
            text(row, "origin_postal_code"),
            text(row, "destination_country_code"),
            text(row, "destination_postal_code"),
            integer(row, "weight_grams"),
            Dimensions(
                integer(row, "width_mm"),
                integer(row, "height_mm"),
                integer(row, "depth_mm"),
            ),
        ),
        QuotationStatus(text(row, "status")),
        instant(row, "created_at"),
        optional_instant(row, "finished_at"),
        ProcessErrorCode(error) if error else None,
        results,
    )


def _decimal(row: D1Row, key: str) -> int:
    value = text(row, key)
    if not value or any(c not in "0123456789" for c in value):
        raise ValueError("Invalid integer text")
    return int(value)


def _results(rows: tuple[D1Row, ...]) -> tuple[ProviderResult, ...]:
    grouped: dict[str, list[D1Row]] = {}
    for row in rows:
        code = optional_text(row, "provider_code")
        if code is not None:
            grouped.setdefault(code, []).append(row)
    results: list[ProviderResult] = []
    for code, stored in grouped.items():
        error = optional_text(stored[0], "error_code")
        offers = tuple(
            ShippingOffer(
                text(row, "service_code"),
                _decimal(row, "price_cents"),
                text(row, "currency"),
                _decimal(row, "transit_days_min"),
                _decimal(row, "transit_days_max"),
            )
            for row in stored
            if row["service_code"] is not None
        )
        results.append(
            ProviderResult(
                code,
                ProviderStatus(text(stored[0], "provider_status")),
                offers,
                ProviderErrorCode(error) if error else None,
            )
        )
    return tuple(results)


class D1QuotationRepository:
    def __init__(self, provider: D1Provider) -> None:
        self.provider = provider

    async def save(self, quotation: Quotation) -> None:
        request = quotation.request
        try:
            await execute(
                self.provider(),
                """
                INSERT INTO shipping_quotations
                (id, origin_country_code, origin_postal_code, destination_country_code,
                 destination_postal_code, weight_grams, width_mm, height_mm, depth_mm,
                 status, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                str(quotation.id),
                request.origin_country_code,
                request.origin_postal_code,
                request.destination_country_code,
                request.destination_postal_code,
                request.weight_grams,
                request.dimensions.width_mm,
                request.dimensions.height_mm,
                request.dimensions.depth_mm,
                quotation.status.value,
                timestamp(quotation.created_at),
            )
        except (D1BindingError, PersistenceError, OSError, ValueError) as cause:
            raise QuotationStorageError("Could not save quotation") from cause

    async def get(self, quotation_id: UUID) -> Quotation | None:
        try:
            rows = await query(self.provider(), _JOINED, str(quotation_id))
            return _quotation(rows[0], _results(rows)) if rows else None
        except (D1BindingError, PersistenceError, OSError, ValueError) as cause:
            raise QuotationStorageError("Could not read quotation") from cause

    async def start(self, quotation_id: UUID) -> Quotation | None:
        try:
            rows = await query(
                self.provider(),
                """
                UPDATE shipping_quotations SET status='PROCESSING'
                WHERE id=? AND status='PENDING' RETURNING *
                """,
                str(quotation_id),
            )
            return _quotation(rows[0]) if rows else None
        except (D1BindingError, PersistenceError, OSError, ValueError) as cause:
            raise QuotationStorageError("Could not start quotation") from cause

    async def complete(
        self,
        quotation_id: UUID,
        results: tuple[ProviderResult, ...],
        finished_at: datetime,
    ) -> None:
        try:
            for result in results:
                result.__post_init__()
            providers = json.dumps(
                [
                    {
                        "provider_code": r.provider_code,
                        "status": r.status.value,
                        "error_code": r.error_code.value if r.error_code else None,
                    }
                    for r in results
                ]
            )
            offers = json.dumps(
                [
                    {
                        "provider_code": r.provider_code,
                        "service_code": o.service_code,
                        "price_cents": o.price_cents,
                        "currency": o.currency,
                        "transit_days_min": o.transit_days_min,
                        "transit_days_max": o.transit_days_max,
                    }
                    for r in results
                    for o in r.offers
                ]
            )
            db = self.provider()
            completed = await batch(
                db,
                [
                    statement(
                        db,
                        """INSERT INTO shipping_provider_results
                    (quotation_id,provider_code,status,error_code)
                    SELECT ?,json_extract(value,'$.provider_code'),json_extract(value,'$.status'),
                    json_extract(value,'$.error_code') FROM json_each(?) WHERE """
                        + _GUARD,
                        str(quotation_id),
                        providers,
                        str(quotation_id),
                    ),
                    statement(
                        db,
                        """INSERT INTO shipping_offers
                    (quotation_id,provider_code,service_code,price_cents,currency,transit_days_min,transit_days_max)
                    SELECT ?,json_extract(value,'$.provider_code'),json_extract(value,'$.service_code'),
                    json_extract(value,'$.price_cents'),json_extract(value,'$.currency'),
                    json_extract(value,'$.transit_days_min'),json_extract(value,'$.transit_days_max')
                    FROM json_each(?) WHERE """
                        + _GUARD,
                        str(quotation_id),
                        offers,
                        str(quotation_id),
                    ),
                    statement(
                        db,
                        """UPDATE shipping_quotations SET status='COMPLETED',finished_at=?
                    WHERE id=? AND status='PROCESSING'""",
                        timestamp(finished_at),
                        str(quotation_id),
                    ),
                ],
            )
            if len(completed) != 3 or completed[2].changes != 1:
                raise QuotationStorageError("Quotation is not processing")
        except (D1BindingError, PersistenceError, OSError, ValueError) as cause:
            raise QuotationStorageError("Could not complete quotation") from cause

    async def fail(
        self,
        quotation_id: UUID,
        expected: QuotationStatus,
        error: ProcessErrorCode,
        finished_at: datetime,
    ) -> None:
        try:
            await execute(
                self.provider(),
                """UPDATE shipping_quotations
                SET status='FAILED',process_error_code=?,finished_at=? WHERE id=? AND status=?""",
                error.value,
                timestamp(finished_at),
                str(quotation_id),
                expected.value,
            )
        except (D1BindingError, PersistenceError, OSError, ValueError) as cause:
            raise QuotationStorageError("Could not record quotation failure") from cause
