"""create dynamic intent registry tables.

Revision ID: 20260521_intent_registry
Revises: 20260520_enable_flags
Create Date: 2026-05-21 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "20260521_intent_registry"
down_revision: Union[str, Sequence[str], None] = "20260520_enable_flags"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "intent_registry" not in tables:
        op.create_table(
            "intent_registry",
            sa.Column("name", sa.String, primary_key=True),
            sa.Column("description", sa.Text, nullable=False, server_default=""),
            sa.Column("required_slots", JSONB, nullable=False, server_default=sa.text("'[]'")),
            sa.Column("optional_slots", JSONB, nullable=False, server_default=sa.text("'[]'")),
            sa.Column("slot_schema", JSONB, nullable=False, server_default=sa.text("'{}'")),
            sa.Column("handler_name", sa.String, nullable=False, server_default=""),
            sa.Column("keywords", JSONB, nullable=False, server_default=sa.text("'[]'")),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
            sa.Column("priority", sa.Integer, nullable=False, server_default="100"),
        )

    if "intent_examples" not in tables:
        op.create_table(
            "intent_examples",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("intent_name", sa.String, nullable=False),
            sa.Column("example_text", sa.Text, nullable=False),
            sa.Column("embedding", JSONB, nullable=True),
            sa.ForeignKeyConstraint(
                ["intent_name"], ["intent_registry.name"], ondelete="CASCADE"
            ),
        )
        op.create_index(
            "ix_intent_examples_intent_name",
            "intent_examples",
            ["intent_name"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    tables = set(insp.get_table_names())

    if "intent_examples" in tables:
        op.drop_index("ix_intent_examples_intent_name", table_name="intent_examples")
        op.drop_table("intent_examples")
    if "intent_registry" in tables:
        op.drop_table("intent_registry")
