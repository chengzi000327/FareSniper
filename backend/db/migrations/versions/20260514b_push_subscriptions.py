"""create push_subscriptions table for WebPush endpoints.

Revision ID: 20260514b_push_subscriptions
Revises: 20260514_alerts
Create Date: 2026-05-14 12:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260514b_push_subscriptions"
down_revision: Union[str, Sequence[str], None] = "20260514_alerts"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "push_subscriptions",
        sa.Column("endpoint", sa.String, primary_key=True),
        sa.Column("user_id", sa.String, nullable=False),
        sa.Column("subscription", sa.JSON, nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_push_subscriptions_user_id", "push_subscriptions", ["user_id"]
    )


def downgrade() -> None:
    op.drop_table("push_subscriptions")
