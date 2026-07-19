"""Persist normalized provider fee and baggage details.

Revision ID: 20260719_offer_fee_details
Revises: 20260718_ctrip_collector
Create Date: 2026-07-19 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "20260719_offer_fee_details"
down_revision: Union[str, Sequence[str], None] = "20260718_ctrip_collector"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "platform_price_snapshots",
        sa.Column("base_price", sa.Integer(), nullable=True),
    )
    op.add_column(
        "platform_price_snapshots",
        sa.Column("tax", sa.Integer(), nullable=True),
    )
    op.add_column(
        "platform_price_snapshots",
        sa.Column("tax_source", sa.String(), nullable=True),
    )
    op.add_column(
        "platform_price_snapshots",
        sa.Column("baggage_fee", sa.Integer(), nullable=True),
    )
    op.add_column(
        "platform_price_snapshots",
        sa.Column("baggage_allowance", sa.String(), nullable=True),
    )
    op.add_column(
        "platform_price_snapshots",
        sa.Column("has_baggage", sa.Boolean(), nullable=True),
    )


def downgrade() -> None:
    for column in (
        "has_baggage",
        "baggage_allowance",
        "baggage_fee",
        "tax_source",
        "tax",
        "base_price",
    ):
        op.drop_column("platform_price_snapshots", column)
