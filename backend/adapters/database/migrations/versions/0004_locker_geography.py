"""Add optional locker geography while preserving aliases and custody."""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None

ADDRESS_COLUMNS = ('country_code', 'postal_code', 'province', 'city', 'street', 'street_number')
GEOGRAPHIC_COLUMNS = ADDRESS_COLUMNS + ('latitude', 'longitude')
ADDRESS_PRESENT = ' AND '.join(f'{name} IS NOT NULL' for name in ADDRESS_COLUMNS)
ADDRESS_ABSENT = ' AND '.join(f'{name} IS NULL' for name in ADDRESS_COLUMNS)
# btrim uses the exact Unicode whitespace set recognized by Python str.strip().
WHITESPACE_SQL = "U&'\\0009\\000a\\000b\\000c\\000d\\001c\\001d\\001e\\001f\\0020\\0085\\00a0\\1680\\2000\\2001\\2002\\2003\\2004\\2005\\2006\\2007\\2008\\2009\\200a\\2028\\2029\\202f\\205f\\3000'"
ADDRESS_VALID = "country_code = 'ES' AND postal_code ~ '^[0-9]{5}$' AND " + ' AND '.join(
    f"btrim({name}, {WHITESPACE_SQL}) <> '' AND {name} = btrim({name}, {WHITESPACE_SQL})"
    for name in ('province', 'city', 'street', 'street_number')
)
ADDRESS_CHECK = f'({ADDRESS_ABSENT}) OR (({ADDRESS_PRESENT}) AND ({ADDRESS_VALID}))'
COORDINATES_CHECK = '(latitude IS NULL AND longitude IS NULL) OR (latitude IS NOT NULL AND longitude IS NOT NULL AND latitude BETWEEN -90 AND 90 AND longitude BETWEEN -180 AND 180)'


def upgrade() -> None:
    for name in ADDRESS_COLUMNS:
        op.add_column('lockers', sa.Column(name, sa.Text(), nullable=True))
    for name in ('latitude', 'longitude'):
        op.add_column('lockers', sa.Column(name, sa.Double(), nullable=True))
    op.alter_column('lockers', 'location_id', existing_type=sa.Text(), nullable=True)
    op.create_check_constraint('ck_lockers_address', 'lockers', ADDRESS_CHECK)
    op.create_check_constraint('ck_lockers_coordinates', 'lockers', COORDINATES_CHECK)


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(sa.text('LOCK TABLE lockers IN ACCESS EXCLUSIVE MODE'))
    geography = ' OR '.join(f'{name} IS NOT NULL' for name in GEOGRAPHIC_COLUMNS)
    if connection.execute(sa.text(f'SELECT 1 FROM lockers WHERE location_id IS NULL OR {geography} LIMIT 1')).first():
        raise RuntimeError('Cannot downgrade locker geography: preserve geographic data and lockers without aliases; arrange an explicit data migration before restoring 0003.')
    op.drop_constraint('ck_lockers_coordinates', 'lockers', type_='check')
    op.drop_constraint('ck_lockers_address', 'lockers', type_='check')
    for name in reversed(GEOGRAPHIC_COLUMNS):
        op.drop_column('lockers', name)
    op.alter_column('lockers', 'location_id', existing_type=sa.Text(), nullable=False)
