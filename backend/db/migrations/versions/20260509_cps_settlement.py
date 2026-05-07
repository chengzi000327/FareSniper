"""create cps_settlements table for affiliate reconciliation.

Revision ID: 20260509_cps_settlement
Revises: 20260508_feature_flags
Create Date: 2026-05-09 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260509_cps_settlement"
down_revision: Union[str, Sequence[str], None] = "20260508_feature_flags"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "cps_settlements",
        sa.Column("order_id", sa.String, primary_key=True),
        sa.Column("platform", sa.String, nullable=False),
        sa.Column("user_id", sa.String, nullable=False, index=True),
        sa.Column("price", sa.Integer, nullable=False),
        sa.Column("commission", sa.Float, nullable=False),
        sa.Column(
            "status", sa.String, nullable=False, server_default="pending"
        ),
    )


def downgrade() -> None:
    op.drop_table("cps_settlements")
