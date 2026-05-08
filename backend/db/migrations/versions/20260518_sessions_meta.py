"""create sessions_meta table.

Revision ID: 20260518_sessions_meta
Revises: 20260517_query_history
Create Date: 2026-05-18 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "20260518_sessions_meta"
down_revision: Union[str, Sequence[str], None] = "20260517_query_history"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "sessions_meta" not in insp.get_table_names():
        op.create_table(
            "sessions_meta",
            sa.Column("session_id", sa.String, primary_key=True),
            sa.Column("user_id", sa.String, nullable=False),
            sa.Column("slots", JSONB, nullable=False, server_default=sa.text("'{}'")),
            sa.Column("turn_count", sa.Integer, nullable=False, server_default="0"),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index(
            "ix_sessions_meta_user_id", "sessions_meta", ["user_id"]
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "sessions_meta" in insp.get_table_names():
        op.drop_index("ix_sessions_meta_user_id", table_name="sessions_meta")
        op.drop_table("sessions_meta")
