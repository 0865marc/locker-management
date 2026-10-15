"""Replace empty legacy tables with parcel custody tables; preserve populated data."""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def _require_empty(direction: str) -> None:
    connection = op.get_bind()
    if connection.dialect.name == "postgresql":
        # Hold both locks until the migration transaction commits or rolls back.
        connection.execute(sa.text("LOCK TABLE deliveries, returns IN ACCESS EXCLUSIVE MODE"))
    populated = [name for name in ("deliveries", "returns")
                 if connection.execute(sa.text(f"SELECT 1 FROM {name} LIMIT 1")).first()]
    if populated:
        explanation = (
            "Legacy rows lack required tracking, carrier, recipient and reception data. "
            if direction == "upgrade" else "Downgrade would lose parcel custody data. "
        )
        raise RuntimeError(
            f"Cannot {direction} parcel schema: populated tables: {', '.join(populated)}. "
            + explanation + "Preserve the database and arrange an explicit data migration with real information."
        )


def upgrade() -> None:
    _require_empty("upgrade")
    op.drop_table("returns")
    op.drop_table("deliveries")
    op.create_table(
        "deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tracking_number", sa.Text(), nullable=False),
        sa.Column("carrier_code", sa.Text(), nullable=False),
        sa.Column("recipient_name", sa.Text(), nullable=False),
        sa.Column("recipient_phone", sa.Text()),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("pickup_deadline_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("collected_at", sa.DateTime(timezone=True)),
        sa.Column("returned_to_carrier_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("(status = 'AWAITING_PICKUP' AND collected_at IS NULL AND returned_to_carrier_at IS NULL) OR (status = 'COLLECTED' AND collected_at IS NOT NULL AND returned_to_carrier_at IS NULL) OR (status = 'RETURNED_TO_CARRIER' AND collected_at IS NULL AND returned_to_carrier_at IS NOT NULL)", name="ck_deliveries_state"),
        sa.CheckConstraint("collected_at IS NULL OR collected_at >= received_at", name="ck_deliveries_collection_time"),
        sa.CheckConstraint("returned_to_carrier_at IS NULL OR returned_to_carrier_at >= received_at", name="ck_deliveries_return_time"),
    )
    op.create_table(
        "returns",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tracking_number", sa.Text(), nullable=False),
        sa.Column("carrier_code", sa.Text(), nullable=False),
        sa.Column("sender_name", sa.Text()),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("handed_over_at", sa.DateTime(timezone=True)),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("(status = 'AWAITING_CARRIER' AND handed_over_at IS NULL) OR (status = 'HANDED_OVER' AND handed_over_at IS NOT NULL)", name="ck_returns_state"),
        sa.CheckConstraint("handed_over_at IS NULL OR handed_over_at >= received_at", name="ck_returns_handover_time"),
    )


def downgrade() -> None:
    _require_empty("downgrade")
    op.drop_table("returns")
    op.drop_table("deliveries")
    op.create_table("deliveries", sa.Column("id", sa.Uuid(), nullable=False),
                    sa.Column("address", sa.Text(), nullable=False), sa.PrimaryKeyConstraint("id"))
    op.create_table("returns", sa.Column("id", sa.Uuid(), nullable=False),
                    sa.Column("reason", sa.Text(), nullable=False), sa.PrimaryKeyConstraint("id"))
