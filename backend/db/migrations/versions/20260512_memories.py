"""create memories table for user preference long-term storage.

Revision ID: 20260512_memories
Revises: 20260511_flight_cache
Create Date: 2026-05-12 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260512_memories"
down_revision: Union[str, Sequence[str], None] = "20260511_flight_cache"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "memories",
        sa.Column("user_id", sa.String, primary_key=True),
        sa.Column("field", sa.String, primary_key=True),
        sa.Column("value", sa.JSON, nullable=False),
        sa.Column("source", sa.String, nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime,
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("memories")
