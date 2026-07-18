"""Add provider-scoped flight snapshots and search demand queue.

Revision ID: 20260716_provider_snapshots
Revises: 20260601_flight_snapshots
Create Date: 2026-07-16 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260716_provider_snapshots"
down_revision: Union[str, Sequence[str], None] = "20260601_flight_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    table_names = set(inspector.get_table_names())
    platform_columns = {
        column["name"]
        for column in inspector.get_columns("platform_price_snapshots")
    }
    provider_columns = (
        sa.Column(
            "data_provider",
            sa.String(),
            nullable=False,
            server_default="legacy",
        ),
        sa.Column(
            "currency",
            sa.String(),
            nullable=False,
            server_default="CNY",
        ),
        sa.Column(
            "price_status",
            sa.String(),
            nullable=False,
            server_default="priced",
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    for column in provider_columns:
        if column.name not in platform_columns:
            op.add_column("platform_price_snapshots", column)

    platform_indexes = {
        index["name"]
        for index in inspector.get_indexes("platform_price_snapshots")
    }
    if "ix_platform_price_provider_flight" not in platform_indexes:
        op.create_index(
            "ix_platform_price_provider_flight",
            "platform_price_snapshots",
            ["data_provider", "flight_snapshot_id"],
        )

    if "flight_search_demands" not in table_names:
        op.create_table(
            "flight_search_demands",
            sa.Column("id", sa.String(), primary_key=True),
            sa.Column("origin_code", sa.String(), nullable=False),
            sa.Column("destination_code", sa.String(), nullable=False),
            sa.Column("depart_date", sa.String(), nullable=False),
            sa.Column(
                "priority", sa.Integer(), nullable=False, server_default="10"
            ),
            sa.Column("source", sa.String(), nullable=False),
            sa.Column(
                "last_requested_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "next_run_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.text("now()"),
            ),
            sa.Column(
                "expires_at", sa.DateTime(timezone=True), nullable=False
            ),
            sa.Column(
                "active", sa.Boolean(), nullable=False, server_default=sa.true()
            ),
            sa.UniqueConstraint(
                "origin_code",
                "destination_code",
                "depart_date",
                name="uq_flight_search_demand_route_date",
            ),
        )
        demand_indexes: set[str] = set()
    else:
        demand_indexes = {
            index["name"]
            for index in inspector.get_indexes("flight_search_demands")
        }
    if "ix_flight_search_demands_due" not in demand_indexes:
        op.create_index(
            "ix_flight_search_demands_due",
            "flight_search_demands",
            ["active", "next_run_at", "priority"],
        )


def downgrade() -> None:
    raise RuntimeError(
        "20260716_provider_snapshots is irreversible: existing provider "
        "schema and flight search demand data may predate Alembic"
    )
