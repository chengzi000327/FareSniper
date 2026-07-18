"""Add Ctrip collector demand leases, nodes, and seller keys.

Revision ID: 20260718_ctrip_collector
Revises: 20260718_provider_inventory
Create Date: 2026-07-18 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_ctrip_collector"
down_revision: Union[str, Sequence[str], None] = (
    "20260718_provider_inventory"
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index(
        "ix_flight_search_demands_due", table_name="flight_search_demands"
    )
    op.drop_constraint(
        "uq_flight_search_demand_route_date",
        "flight_search_demands",
        type_="unique",
    )

    op.add_column(
        "flight_search_demands",
        sa.Column("demand_hour", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "flight_search_demands",
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "flight_search_demands",
        sa.Column(
            "attempts", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.add_column(
        "flight_search_demands",
        sa.Column(
            "next_attempt_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "flight_search_demands",
        sa.Column("lease_owner", sa.String(), nullable=True),
    )
    op.add_column(
        "flight_search_demands",
        sa.Column(
            "lease_expires_at", sa.DateTime(timezone=True), nullable=True
        ),
    )
    op.add_column(
        "flight_search_demands",
        sa.Column("last_error", sa.Text(), nullable=True),
    )
    op.add_column(
        "flight_search_demands",
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "flight_search_demands",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.execute(
        """
        UPDATE flight_search_demands
        SET demand_hour = date_trunc('hour', last_requested_at),
            next_attempt_at = next_run_at,
            created_at = last_requested_at,
            updated_at = last_requested_at
        """
    )
    op.alter_column(
        "flight_search_demands", "demand_hour", nullable=False
    )
    op.alter_column(
        "flight_search_demands", "next_attempt_at", nullable=False
    )
    op.alter_column("flight_search_demands", "created_at", nullable=False)
    op.alter_column("flight_search_demands", "updated_at", nullable=False)
    op.create_unique_constraint(
        "uq_flight_search_demand_hour",
        "flight_search_demands",
        ["origin_code", "destination_code", "depart_date", "demand_hour"],
    )
    op.create_index(
        "ix_flight_search_demands_due",
        "flight_search_demands",
        ["active", "status", "next_attempt_at", "priority"],
    )

    op.create_table(
        "collector_nodes",
        sa.Column("node_id", sa.String(), primary_key=True),
        sa.Column("version", sa.String(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column(
            "last_heartbeat", sa.DateTime(timezone=True), nullable=False
        ),
        sa.Column("last_success", sa.DateTime(timezone=True), nullable=True),
    )

    op.execute(
        """
        DELETE FROM platform_price_snapshots AS duplicate
        USING platform_price_snapshots AS keeper
        WHERE duplicate.flight_snapshot_id = keeper.flight_snapshot_id
          AND duplicate.data_provider = keeper.data_provider
          AND duplicate.platform = keeper.platform
          AND (
              duplicate.crawled_at < keeper.crawled_at
              OR (
                  duplicate.crawled_at = keeper.crawled_at
                  AND duplicate.id > keeper.id
              )
          )
        """
    )
    op.create_unique_constraint(
        "uq_platform_price_provider_seller",
        "platform_price_snapshots",
        ["flight_snapshot_id", "data_provider", "platform"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_platform_price_provider_seller",
        "platform_price_snapshots",
        type_="unique",
    )
    op.drop_table("collector_nodes")

    op.drop_index(
        "ix_flight_search_demands_due", table_name="flight_search_demands"
    )
    op.drop_constraint(
        "uq_flight_search_demand_hour",
        "flight_search_demands",
        type_="unique",
    )
    op.execute(
        """
        DELETE FROM flight_search_demands AS duplicate
        USING flight_search_demands AS keeper
        WHERE duplicate.origin_code = keeper.origin_code
          AND duplicate.destination_code = keeper.destination_code
          AND duplicate.depart_date = keeper.depart_date
          AND (
              duplicate.priority < keeper.priority
              OR (
                  duplicate.priority = keeper.priority
                  AND duplicate.last_requested_at < keeper.last_requested_at
              )
              OR (
                  duplicate.priority = keeper.priority
                  AND duplicate.last_requested_at = keeper.last_requested_at
                  AND duplicate.id > keeper.id
              )
          )
        """
    )
    op.create_unique_constraint(
        "uq_flight_search_demand_route_date",
        "flight_search_demands",
        ["origin_code", "destination_code", "depart_date"],
    )
    op.create_index(
        "ix_flight_search_demands_due",
        "flight_search_demands",
        ["active", "next_run_at", "priority"],
    )

    op.drop_column("flight_search_demands", "updated_at")
    op.drop_column("flight_search_demands", "created_at")
    op.drop_column("flight_search_demands", "last_error")
    op.drop_column("flight_search_demands", "lease_expires_at")
    op.drop_column("flight_search_demands", "lease_owner")
    op.drop_column("flight_search_demands", "next_attempt_at")
    op.drop_column("flight_search_demands", "attempts")
    op.drop_column("flight_search_demands", "status")
    op.drop_column("flight_search_demands", "demand_hour")
