"""Add provider inventory refresh observations.

Revision ID: 20260718_provider_inventory
Revises: 20260716_provider_snapshots
Create Date: 2026-07-18 00:00:00.000000
"""
from __future__ import annotations

import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_provider_inventory"
down_revision: Union[str, Sequence[str], None] = "20260716_provider_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_ITEM_COUNT_CHECK_NAME = "ck_provider_inventory_observation_item_count"


def _is_nonnegative_item_count_check(sqltext: object) -> bool:
    if not isinstance(sqltext, str):
        return False
    normalized = re.sub(r"\s+", "", sqltext.lower()).replace('"', "")
    normalized = re.sub(
        r"::(?:smallint|integer|bigint|numeric(?:\(\d+(?:,\d+)?\))?)",
        "",
        normalized,
    )
    normalized = normalized.replace("(", "").replace(")", "")
    return normalized in {"item_count>=0", "0<=item_count"}


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    if "provider_inventory_observations" not in inspector.get_table_names():
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
                name=_ITEM_COUNT_CHECK_NAME,
            ),
        )
        return

    check_constraints = inspector.get_check_constraints(
        "provider_inventory_observations"
    )
    named_check = next(
        (
            constraint
            for constraint in check_constraints
            if constraint.get("name") == _ITEM_COUNT_CHECK_NAME
        ),
        None,
    )
    if named_check is None:
        op.create_check_constraint(
            _ITEM_COUNT_CHECK_NAME,
            "provider_inventory_observations",
            "item_count >= 0",
        )
    elif not _is_nonnegative_item_count_check(named_check.get("sqltext")):
        raise RuntimeError(
            f"{_ITEM_COUNT_CHECK_NAME} has a mismatched definition; "
            "refusing to alter the existing table"
        )


def downgrade() -> None:
    raise RuntimeError(
        "20260718_provider_inventory is irreversible: provider inventory "
        "schema and data may predate Alembic"
    )
