"""create analytics_events table for telemetry pipeline.

Revision ID: 20260506_analytics_events
Revises: 20260505_init
Create Date: 2026-05-06 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260506_analytics_events"
down_revision: Union[str, Sequence[str], None] = "20260505_init"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "analytics_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("event_name", sa.String, nullable=False, index=True),
        sa.Column("user_id", sa.String, nullable=False, index=True),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
            index=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("analytics_events")
