"""create feature_flags table and seed three differentiation flags.

Revision ID: 20260508_feature_flags
Revises: 20260507_metrics_views
Create Date: 2026-05-08 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260508_feature_flags"
down_revision: Union[str, Sequence[str], None] = "20260507_metrics_views"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "feature_flags",
        sa.Column("name", sa.String, primary_key=True),
        sa.Column(
            "enabled", sa.Boolean, nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "rollout_pct", sa.Integer, nullable=False, server_default="0"
        ),
    )
    # Seed the three PRD §4.2 differentiation flags as disabled at 0% rollout.
    seed = sa.table(
        "feature_flags",
        sa.column("name", sa.String),
        sa.column("enabled", sa.Boolean),
        sa.column("rollout_pct", sa.Integer),
    )
    op.bulk_insert(
        seed,
        [
            {"name": "ai_value_judge", "enabled": False, "rollout_pct": 0},
            {"name": "multi_platform_aggregation", "enabled": False, "rollout_pct": 0},
            {"name": "preference_memory", "enabled": False, "rollout_pct": 0},
        ],
    )


def downgrade() -> None:
    op.drop_table("feature_flags")
