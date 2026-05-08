"""price_history table

Revision ID: 20260515_price_history
Revises: 20260518_sessions_meta
Create Date: 2026-05-15 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "20260515_price_history"
down_revision = "20260518_sessions_meta"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "price_history" not in inspector.get_table_names():
        op.create_table(
            "price_history",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("origin", sa.String, nullable=False),
            sa.Column("destination", sa.String, nullable=False),
            sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("min_price", sa.Integer, nullable=False),
        )
        op.create_index("ix_price_history_origin", "price_history", ["origin"])
        op.create_index("ix_price_history_destination", "price_history", ["destination"])
        op.create_index("ix_price_history_snapshot_at", "price_history", ["snapshot_at"])


def downgrade() -> None:
    op.drop_table("price_history")
