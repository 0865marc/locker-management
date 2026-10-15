"""Add physical capacity and shared assignment history without rewriting parcels."""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('lockers', sa.Column('id', sa.Uuid(), primary_key=True),
                    sa.Column('location_id', sa.Text(), nullable=False), sa.Column('active', sa.Boolean(), nullable=False))
    op.create_index('ix_lockers_location_id', 'lockers', ['location_id'])
    op.create_table('locker_compartments', sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('locker_id', sa.Uuid(), sa.ForeignKey('lockers.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('width_mm', sa.Integer(), nullable=False), sa.Column('height_mm', sa.Integer(), nullable=False), sa.Column('depth_mm', sa.Integer(), nullable=False),
        sa.Column('enabled', sa.Boolean(), nullable=False), sa.Column('retired', sa.Boolean(), nullable=False),
        sa.CheckConstraint('width_mm BETWEEN 1 AND 2147483647 AND height_mm BETWEEN 1 AND 2147483647 AND depth_mm BETWEEN 1 AND 2147483647', name='ck_compartments_dimensions'),
        sa.CheckConstraint('NOT (retired AND enabled)', name='ck_compartments_retired'))
    op.create_index('ix_locker_compartments_locker_id', 'locker_compartments', ['locker_id'])
    op.create_table('locker_assignments', sa.Column('id', sa.Uuid(), primary_key=True),
        sa.Column('compartment_id', sa.Uuid(), sa.ForeignKey('locker_compartments.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('delivery_id', sa.Uuid(), sa.ForeignKey('deliveries.id', ondelete='RESTRICT')),
        sa.Column('return_id', sa.Uuid(), sa.ForeignKey('returns.id', ondelete='RESTRICT')),
        sa.Column('width_mm', sa.Integer(), nullable=False), sa.Column('height_mm', sa.Integer(), nullable=False), sa.Column('depth_mm', sa.Integer(), nullable=False),
        sa.Column('assigned_at', sa.DateTime(timezone=True), nullable=False), sa.Column('released_at', sa.DateTime(timezone=True)),
        sa.CheckConstraint('(delivery_id IS NOT NULL AND return_id IS NULL) OR (delivery_id IS NULL AND return_id IS NOT NULL)', name='ck_assignments_parcel'),
        sa.CheckConstraint('width_mm BETWEEN 1 AND 2147483647 AND height_mm BETWEEN 1 AND 2147483647 AND depth_mm BETWEEN 1 AND 2147483647', name='ck_assignments_dimensions'),
        sa.CheckConstraint('released_at IS NULL OR released_at >= assigned_at', name='ck_assignments_release_time'),
        sa.UniqueConstraint('delivery_id', name='uq_assignments_delivery'), sa.UniqueConstraint('return_id', name='uq_assignments_return'))
    op.create_index('uq_assignments_active_compartment', 'locker_assignments', ['compartment_id'], unique=True,
                    postgresql_where=sa.text('released_at IS NULL'), sqlite_where=sa.text('released_at IS NULL'))


def downgrade():
    connection = op.get_bind()
    names = ('lockers', 'locker_compartments', 'locker_assignments')
    if connection.dialect.name == 'postgresql':
        connection.execute(sa.text('LOCK TABLE lockers, locker_compartments, locker_assignments IN ACCESS EXCLUSIVE MODE'))
    populated = [name for name in names if connection.execute(sa.text(f'SELECT 1 FROM {name} LIMIT 1')).first()]
    if populated:
        raise RuntimeError('Cannot downgrade populated locker tables: ' + ', '.join(populated) + '. Preserve the database and arrange an explicit data migration.')
    op.drop_table('locker_assignments')
    op.drop_table('locker_compartments')
    op.drop_table('lockers')
