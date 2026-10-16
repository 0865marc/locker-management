"""Add persistent shipping quotations without changing earlier business data."""
from alembic import op
from sqlalchemy import (Table, Column, Uuid, Text, Integer, DateTime, CheckConstraint,
                        ForeignKeyConstraint, MetaData, text)

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None
metadata = MetaData()

REQUEST_CHECK = "origin_country_code = 'ES' AND destination_country_code = 'ES' AND origin_postal_code ~ '^[0-9]{5}$' AND destination_postal_code ~ '^[0-9]{5}$' AND weight_grams BETWEEN 1 AND 30000 AND width_mm BETWEEN 1 AND 2000 AND height_mm BETWEEN 1 AND 2000 AND depth_mm BETWEEN 1 AND 2000"
STATE_CHECK = "(status IN ('PENDING','PROCESSING') AND finished_at IS NULL AND process_error_code IS NULL) OR (status = 'COMPLETED' AND finished_at IS NOT NULL AND process_error_code IS NULL) OR (status = 'FAILED' AND finished_at IS NOT NULL AND process_error_code IS NOT NULL AND process_error_code IN ('PUBLISH_ERROR','PROCESSING_ERROR'))"
RESULT_CHECK = "(status = 'QUOTED' AND error_code IS NULL) OR (status = 'NOT_COVERED' AND error_code IS NULL) OR (status = 'FAILED' AND error_code IS NOT NULL AND error_code IN ('PROVIDER_ERROR','PROVIDER_TIMEOUT'))"

_quotations = Table('shipping_quotations', metadata,
    Column('id', Uuid(), primary_key=True),
    *(Column(name, Text, nullable=False) for name in ('origin_country_code', 'origin_postal_code', 'destination_country_code', 'destination_postal_code')),
    *(Column(name, Integer, nullable=False) for name in ('weight_grams', 'width_mm', 'height_mm', 'depth_mm')),
    Column('status', Text, nullable=False), Column('created_at', DateTime(timezone=True), nullable=False),
    Column('finished_at', DateTime(timezone=True)), Column('process_error_code', Text),
    CheckConstraint(REQUEST_CHECK, name='ck_shipping_quotations_request'),
    CheckConstraint(STATE_CHECK, name='ck_shipping_quotations_state'),
    CheckConstraint('finished_at IS NULL OR finished_at >= created_at', name='ck_shipping_quotations_time'))
_results = Table('shipping_provider_results', metadata,
    Column('quotation_id', Uuid(), primary_key=True), Column('provider_code', Text, primary_key=True),
    Column('status', Text, nullable=False), Column('error_code', Text),
    ForeignKeyConstraint(['quotation_id'], ['shipping_quotations.id']),
    CheckConstraint("provider_code <> '' AND provider_code = btrim(provider_code)", name='ck_shipping_results_provider'),
    CheckConstraint(RESULT_CHECK, name='ck_shipping_results_state'))
_offers = Table('shipping_offers', metadata,
    Column('quotation_id', Uuid(), primary_key=True), Column('provider_code', Text, primary_key=True),
    Column('service_code', Text, primary_key=True), Column('price_cents', Integer, nullable=False),
    Column('currency', Text, nullable=False), Column('transit_days_min', Integer, nullable=False), Column('transit_days_max', Integer, nullable=False),
    ForeignKeyConstraint(['quotation_id', 'provider_code'], ['shipping_provider_results.quotation_id', 'shipping_provider_results.provider_code']),
    CheckConstraint("service_code <> '' AND service_code = btrim(service_code) AND price_cents > 0 AND currency = 'EUR' AND transit_days_min > 0 AND transit_days_max >= transit_days_min", name='ck_shipping_offers_values'))



def upgrade() -> None:
    metadata.create_all(op.get_bind())


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(text('LOCK TABLE shipping_quotations, shipping_provider_results, shipping_offers IN ACCESS EXCLUSIVE MODE'))
    for table in ('shipping_quotations', 'shipping_provider_results', 'shipping_offers'):
        if connection.execute(text(f'SELECT 1 FROM {table} LIMIT 1')).first():
            raise RuntimeError('Cannot downgrade quotations: preserve quotation data; arrange an explicit data migration before restoring 0004.')
    metadata.drop_all(connection)
