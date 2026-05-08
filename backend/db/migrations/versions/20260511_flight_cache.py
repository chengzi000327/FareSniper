"""create flight_cache table for hourly scraper output.

Revision ID: 20260511_flight_cache
Revises: 20260510_hypothesis_views
Create Date: 2026-05-11 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260511_flight_cache"
down_revision: Union[str, Sequence[str], None] = "20260510_hypothesis_views"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "flight_cache",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("origin", sa.String, nullable=False),
        sa.Column("destination", sa.String, nullable=False),
        sa.Column("depart_date", sa.String, nullable=False),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column(
            "fetched_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_flight_cache_origin", "flight_cache", ["origin"])
    op.create_index("ix_flight_cache_destination", "flight_cache", ["destination"])
    op.create_index("ix_flight_cache_depart_date", "flight_cache", ["depart_date"])
    op.create_index(
        "ix_flight_cache_lookup",
        "flight_cache",
        ["origin", "destination", "depart_date", "fetched_at"],
    )


def downgrade() -> None:
    op.drop_table("flight_cache")
