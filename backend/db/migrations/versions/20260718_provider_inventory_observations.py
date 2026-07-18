"""Add provider inventory refresh observations.

Revision ID: 20260718_provider_inventory
Revises: 20260716_provider_snapshots
Create Date: 2026-07-18 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_provider_inventory"
down_revision: Union[str, Sequence[str], None] = "20260716_provider_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "provider_inventory_observations",
        sa.Column("provider", sa.String(), primary_key=True),
        sa.Column("origin_code", sa.String(), primary_key=True),
        sa.Column("destination_code", sa.String(), primary_key=True),
        sa.Column("depart_date", sa.String(), primary_key=True),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("item_count", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "item_count >= 0",
            name="ck_provider_inventory_observation_item_count",
        ),
    )


def downgrade() -> None:
    op.drop_table("provider_inventory_observations")
