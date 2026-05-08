"""promotions table

Revision ID: 20260516_promotions
Revises: 20260515_price_history
Create Date: 2026-05-16 00:00:00
"""
from alembic import op
import sqlalchemy as sa

revision = "20260516_promotions"
down_revision = "20260515_price_history"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "promotions",
        sa.Column("platform", sa.String, primary_key=True),
        sa.Column("flight_no", sa.String, primary_key=True),
        sa.Column("date", sa.String, primary_key=True),
        sa.Column("discount_pct", sa.Integer, nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table("promotions")
