"""ensure query_history table exists with required columns and indexes.

Revision ID: 20260517_query_history
Revises: 20260514b_push_subscriptions
Create Date: 2026-05-17 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260517_query_history"
down_revision: Union[str, Sequence[str], None] = "20260514b_push_subscriptions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "query_history" not in insp.get_table_names():
        op.create_table(
            "query_history",
            sa.Column("id", sa.Integer, primary_key=True),
            sa.Column("user_id", sa.String, nullable=False),
            sa.Column("query_text", sa.String, nullable=False),
            sa.Column(
                "intent",
                sa.JSON,
                nullable=False,
                server_default=sa.text("'{}'"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime,
                nullable=False,
                server_default=sa.func.now(),
            ),
        )
        op.create_index(
            "ix_query_history_user_id", "query_history", ["user_id"]
        )
        op.create_index(
            "ix_query_history_created_at", "query_history", ["created_at"]
        )
    else:
        cols = {c["name"] for c in insp.get_columns("query_history")}
        if "intent" not in cols:
            op.add_column(
                "query_history",
                sa.Column(
                    "intent",
                    sa.JSON,
                    nullable=False,
                    server_default=sa.text("'{}'"),
                ),
            )
        index_names = {idx["name"] for idx in insp.get_indexes("query_history")}
        if "ix_query_history_user_id" not in index_names:
            op.create_index(
                "ix_query_history_user_id", "query_history", ["user_id"]
            )
        if "ix_query_history_created_at" not in index_names:
            op.create_index(
                "ix_query_history_created_at", "query_history", ["created_at"]
            )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if "query_history" in insp.get_table_names():
        index_names = {idx["name"] for idx in insp.get_indexes("query_history")}
        if "ix_query_history_created_at" in index_names:
            op.drop_index(
                "ix_query_history_created_at", table_name="query_history"
            )
