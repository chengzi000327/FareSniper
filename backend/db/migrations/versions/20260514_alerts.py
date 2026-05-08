"""create alerts table for price monitoring.

Revision ID: 20260514_alerts
Revises: 20260513_users
Create Date: 2026-05-14 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260514_alerts"
down_revision: Union[str, Sequence[str], None] = "20260513_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "alerts",
        sa.Column("id", sa.String, primary_key=True),
        sa.Column("user_id", sa.String, nullable=False),
        sa.Column("origin", sa.String, nullable=False),
        sa.Column("destination", sa.String, nullable=False),
        sa.Column("depart_date", sa.String, nullable=False),
        sa.Column("target_price", sa.Integer, nullable=False),
        sa.Column("status", sa.String, nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_alerts_user_id", "alerts", ["user_id"])


def downgrade() -> None:
    op.drop_table("alerts")
