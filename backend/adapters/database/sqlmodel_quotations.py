"""One transaction per state change; completed batches are read under a row lock."""
from datetime import datetime
from typing import ClassVar
from uuid import UUID

from sqlalchemy import (Table, Column, Uuid, Text, Integer, DateTime, CheckConstraint,
                        ForeignKeyConstraint)
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlmodel import SQLModel, Field, select
from sqlmodel.ext.asyncio.session import AsyncSession

from application.quotation_models import Quotation, QuotationStatus, ProcessErrorCode, QuotationStorageError
from application.shipping_quotes import ProviderResult, ProviderStatus, ProviderErrorCode
from domain.shipping_quotes import ShippingQuoteRequest, ShippingOffer
from domain.lockers import Dimensions

REQUEST_CHECK = "origin_country_code = 'ES' AND destination_country_code = 'ES' AND origin_postal_code ~ '^[0-9]{5}$' AND destination_postal_code ~ '^[0-9]{5}$' AND weight_grams BETWEEN 1 AND 30000 AND width_mm BETWEEN 1 AND 2000 AND height_mm BETWEEN 1 AND 2000 AND depth_mm BETWEEN 1 AND 2000"
STATE_CHECK = "(status IN ('PENDING','PROCESSING') AND finished_at IS NULL AND process_error_code IS NULL) OR (status = 'COMPLETED' AND finished_at IS NOT NULL AND process_error_code IS NULL) OR (status = 'FAILED' AND finished_at IS NOT NULL AND process_error_code IS NOT NULL AND process_error_code IN ('PUBLISH_ERROR','PROCESSING_ERROR'))"
RESULT_CHECK = "(status = 'QUOTED' AND error_code IS NULL) OR (status = 'NOT_COVERED' AND error_code IS NULL) OR (status = 'FAILED' AND error_code IS NOT NULL AND error_code IN ('PROVIDER_ERROR','PROVIDER_TIMEOUT'))"

_quotations = Table('shipping_quotations', SQLModel.metadata,
    Column('id', Uuid(), primary_key=True),
    *(Column(name, Text, nullable=False) for name in ('origin_country_code', 'origin_postal_code', 'destination_country_code', 'destination_postal_code')),
    *(Column(name, Integer, nullable=False) for name in ('weight_grams', 'width_mm', 'height_mm', 'depth_mm')),
    Column('status', Text, nullable=False), Column('created_at', DateTime(timezone=True), nullable=False),
    Column('finished_at', DateTime(timezone=True)), Column('process_error_code', Text),
    CheckConstraint(REQUEST_CHECK, name='ck_shipping_quotations_request'),
    CheckConstraint(STATE_CHECK, name='ck_shipping_quotations_state'),
    CheckConstraint('finished_at IS NULL OR finished_at >= created_at', name='ck_shipping_quotations_time'))
_results = Table('shipping_provider_results', SQLModel.metadata,
    Column('quotation_id', Uuid(), primary_key=True), Column('provider_code', Text, primary_key=True),
    Column('status', Text, nullable=False), Column('error_code', Text),
    ForeignKeyConstraint(['quotation_id'], ['shipping_quotations.id']),
    CheckConstraint("provider_code <> '' AND provider_code = btrim(provider_code)", name='ck_shipping_results_provider'),
    CheckConstraint(RESULT_CHECK, name='ck_shipping_results_state'))
_offers = Table('shipping_offers', SQLModel.metadata,
    Column('quotation_id', Uuid(), primary_key=True), Column('provider_code', Text, primary_key=True),
    Column('service_code', Text, primary_key=True), Column('price_cents', Integer, nullable=False),
    Column('currency', Text, nullable=False), Column('transit_days_min', Integer, nullable=False), Column('transit_days_max', Integer, nullable=False),
    ForeignKeyConstraint(['quotation_id', 'provider_code'], ['shipping_provider_results.quotation_id', 'shipping_provider_results.provider_code']),
    CheckConstraint("service_code <> '' AND service_code = btrim(service_code) AND price_cents > 0 AND currency = 'EUR' AND transit_days_min > 0 AND transit_days_max >= transit_days_min", name='ck_shipping_offers_values'))


class QuotationRow(SQLModel, table=True):
    __table__: ClassVar[Table] = _quotations
    id: UUID = Field(sa_column=_quotations.c.id)
    origin_country_code: str = Field(sa_column=_quotations.c.origin_country_code)
    origin_postal_code: str = Field(sa_column=_quotations.c.origin_postal_code)
    destination_country_code: str = Field(sa_column=_quotations.c.destination_country_code)
    destination_postal_code: str = Field(sa_column=_quotations.c.destination_postal_code)
    weight_grams: int = Field(sa_column=_quotations.c.weight_grams)
    width_mm: int = Field(sa_column=_quotations.c.width_mm)
    height_mm: int = Field(sa_column=_quotations.c.height_mm)
    depth_mm: int = Field(sa_column=_quotations.c.depth_mm)
    status: str = Field(sa_column=_quotations.c.status)
    created_at: datetime = Field(sa_column=_quotations.c.created_at)
    finished_at: datetime | None = Field(default=None, sa_column=_quotations.c.finished_at)
    process_error_code: str | None = Field(default=None, sa_column=_quotations.c.process_error_code)


class ProviderResultRow(SQLModel, table=True):
    __table__: ClassVar[Table] = _results
    quotation_id: UUID = Field(sa_column=_results.c.quotation_id)
    provider_code: str = Field(sa_column=_results.c.provider_code)
    status: str = Field(sa_column=_results.c.status)
    error_code: str | None = Field(default=None, sa_column=_results.c.error_code)


class OfferRow(SQLModel, table=True):
    __table__: ClassVar[Table] = _offers
    quotation_id: UUID = Field(sa_column=_offers.c.quotation_id)
    provider_code: str = Field(sa_column=_offers.c.provider_code)
    service_code: str = Field(sa_column=_offers.c.service_code)
    price_cents: int = Field(sa_column=_offers.c.price_cents)
    currency: str = Field(sa_column=_offers.c.currency)
    transit_days_min: int = Field(sa_column=_offers.c.transit_days_min)
    transit_days_max: int = Field(sa_column=_offers.c.transit_days_max)


def _quotation(row: QuotationRow, results: tuple[ProviderResult, ...] = ()) -> Quotation:
    return Quotation(row.id, ShippingQuoteRequest(row.origin_country_code, row.origin_postal_code,
        row.destination_country_code, row.destination_postal_code, row.weight_grams,
        Dimensions(row.width_mm, row.height_mm, row.depth_mm)), QuotationStatus(row.status),
        row.created_at, row.finished_at,
        ProcessErrorCode(row.process_error_code) if row.process_error_code else None, results)


class SqlModelQuotationRepository:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def save(self, quotation: Quotation) -> None:
        request = quotation.request
        try:
            async with self.sessions.begin() as session:
                session.add(QuotationRow(id=quotation.id, origin_country_code=request.origin_country_code,
                    origin_postal_code=request.origin_postal_code, destination_country_code=request.destination_country_code,
                    destination_postal_code=request.destination_postal_code, weight_grams=request.weight_grams,
                    width_mm=request.dimensions.width_mm, height_mm=request.dimensions.height_mm,
                    depth_mm=request.dimensions.depth_mm, status=quotation.status.value, created_at=quotation.created_at))
        except Exception as error:
            raise QuotationStorageError('Could not save quotation') from error

    async def get(self, quotation_id: UUID) -> Quotation | None:
        try:
            async with self.sessions.begin() as session:
                row = (await session.exec(select(QuotationRow).where(QuotationRow.id == quotation_id).with_for_update(read=True))).first()
                if row is None:
                    return None
                results: list[ProviderResult] = []
                stored = await session.exec(select(ProviderResultRow).where(ProviderResultRow.quotation_id == quotation_id).order_by(ProviderResultRow.provider_code))
                for result in stored:
                    offers = await session.exec(select(OfferRow).where(OfferRow.quotation_id == quotation_id, OfferRow.provider_code == result.provider_code).order_by(OfferRow.service_code))
                    results.append(ProviderResult(result.provider_code, ProviderStatus(result.status),
                        tuple(ShippingOffer(offer.service_code, offer.price_cents, offer.currency, offer.transit_days_min, offer.transit_days_max) for offer in offers),
                        ProviderErrorCode(result.error_code) if result.error_code else None))
                return _quotation(row, tuple(results))
        except Exception as error:
            raise QuotationStorageError('Could not read quotation') from error

    async def start(self, quotation_id: UUID) -> Quotation | None:
        try:
            async with self.sessions.begin() as session:
                row = (await session.exec(select(QuotationRow).where(QuotationRow.id == quotation_id).with_for_update())).first()
                if row is None or row.status != QuotationStatus.PENDING.value:
                    return None
                row.status = QuotationStatus.PROCESSING.value
                session.add(row)
                return _quotation(row)
        except Exception as error:
            raise QuotationStorageError('Could not start quotation') from error

    async def complete(self, quotation_id: UUID, results: tuple[ProviderResult, ...], finished_at: datetime) -> None:
        try:
            async with self.sessions.begin() as session:
                row = (await session.exec(select(QuotationRow).where(QuotationRow.id == quotation_id).with_for_update())).one()
                if row.status != QuotationStatus.PROCESSING.value:
                    raise QuotationStorageError('Quotation is not processing')
                for result in results:
                    result.__post_init__()
                    session.add(ProviderResultRow(quotation_id=quotation_id, provider_code=result.provider_code,
                        status=result.status.value, error_code=result.error_code.value if result.error_code else None))
                await session.flush()
                for result in results:
                    for offer in result.offers:
                        session.add(OfferRow(quotation_id=quotation_id, provider_code=result.provider_code,
                            service_code=offer.service_code, price_cents=offer.price_cents, currency=offer.currency,
                            transit_days_min=offer.transit_days_min, transit_days_max=offer.transit_days_max))
                row.status = QuotationStatus.COMPLETED.value
                row.finished_at = finished_at
                session.add(row)
        except Exception as error:
            raise QuotationStorageError('Could not complete quotation') from error

    async def fail(self, quotation_id: UUID, expected: QuotationStatus, error: ProcessErrorCode, finished_at: datetime) -> None:
        try:
            async with self.sessions.begin() as session:
                row = (await session.exec(select(QuotationRow).where(QuotationRow.id == quotation_id).with_for_update())).first()
                if row is not None and row.status == expected.value:
                    row.status = QuotationStatus.FAILED.value
                    row.process_error_code = error.value
                    row.finished_at = finished_at
                    session.add(row)
        except Exception as cause:
            raise QuotationStorageError('Could not record quotation failure') from cause
