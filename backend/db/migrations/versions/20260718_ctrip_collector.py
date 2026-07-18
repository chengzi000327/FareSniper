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

_COLLECTOR_NODE_COLUMNS = {
    "node_id": ("VARCHAR", False),
    "version": ("VARCHAR", False),
    "status": ("VARCHAR", False),
    "last_heartbeat": ("TIMESTAMP WITH TIME ZONE", False),
    "last_success": ("TIMESTAMP WITH TIME ZONE", True),
}


def _column_type_name(column_type: sa.types.TypeEngine) -> str:
    if isinstance(column_type, sa.VARCHAR):
        if column_type.length is None:
            return "VARCHAR"
        return f"VARCHAR({column_type.length})"
    if isinstance(column_type, sa.TIMESTAMP):
        timezone = "WITH" if column_type.timezone else "WITHOUT"
        return f"TIMESTAMP {timezone} TIME ZONE"
    return str(column_type)


def _collector_nodes_table_exists() -> bool:
    inspector = sa.inspect(op.get_bind())
    if "collector_nodes" not in inspector.get_table_names():
        return False

    columns = inspector.get_columns("collector_nodes")
    columns_by_name = {column["name"]: column for column in columns}
    errors: list[str] = []
    if set(columns_by_name) != set(_COLLECTOR_NODE_COLUMNS):
        errors.append(
            "columns must be exactly "
            f"{list(_COLLECTOR_NODE_COLUMNS)}; found {list(columns_by_name)}"
        )

    for name, (expected_type, expected_nullable) in (
        _COLLECTOR_NODE_COLUMNS.items()
    ):
        column = columns_by_name.get(name)
        if column is None:
            continue
        actual_type = _column_type_name(column["type"])
        actual_nullable = bool(column["nullable"])
        has_default = column.get("default") is not None
        if (
            actual_type != expected_type
            or actual_nullable != expected_nullable
            or has_default
        ):
            expected_nullability = "NULL" if expected_nullable else "NOT NULL"
            actual_nullability = "NULL" if actual_nullable else "NOT NULL"
            actual_default = (
                f" default {column['default']}" if has_default else ""
            )
            errors.append(
                f"column {name!r} must be {expected_type} "
                f"{expected_nullability} with no default; found "
                f"{actual_type} {actual_nullability}{actual_default}"
            )

    primary_key = inspector.get_pk_constraint("collector_nodes")
    primary_key_columns = primary_key.get("constrained_columns") or []
    if primary_key_columns != ["node_id"]:
        errors.append(
            "primary key must be exactly ['node_id']; "
            f"found {primary_key_columns}"
        )

    if errors:
        raise RuntimeError(
            "collector_nodes has incompatible schema: "
            + "; ".join(errors)
            + "; refusing to adopt the existing table"
        )
    return True


def upgrade() -> None:
    collector_nodes_exists = _collector_nodes_table_exists()

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
        sa.Column(
            "origin_airport_code",
            sa.String(),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "flight_search_demands",
        sa.Column(
            "destination_airport_code",
            sa.String(),
            nullable=False,
            server_default="",
        ),
    )
    op.add_column(
        "flight_search_demands",
        sa.Column(
            "demand_hour",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text(
                "'1970-01-01 00:00:00+00'::timestamptz"
            ),
        ),
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
            server_default=sa.text("now()"),
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
            server_default=sa.text("now()"),
        ),
    )
    op.add_column(
        "flight_search_demands",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
            server_default=sa.text("now()"),
        ),
    )
    op.execute(
        """
        UPDATE flight_search_demands
        SET demand_hour = '1970-01-01 00:00:00+00'::timestamptz,
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
        [
            "origin_code",
            "origin_airport_code",
            "destination_code",
            "destination_airport_code",
            "depart_date",
            "demand_hour",
        ],
    )
    op.create_unique_constraint(
        "uq_flight_search_demand_route_date",
        "flight_search_demands",
        [
            "origin_code",
            "origin_airport_code",
            "destination_code",
            "destination_airport_code",
            "depart_date",
            "demand_hour",
        ],
    )
    op.create_index(
        "ix_flight_search_demands_due",
        "flight_search_demands",
        ["active", "status", "next_attempt_at", "priority"],
    )

    if not collector_nodes_exists:
        op.create_table(
            "collector_nodes",
            sa.Column("node_id", sa.String(), primary_key=True),
            sa.Column("version", sa.String(), nullable=False),
            sa.Column("status", sa.String(), nullable=False),
            sa.Column(
                "last_heartbeat", sa.DateTime(timezone=True), nullable=False
            ),
            sa.Column(
                "last_success", sa.DateTime(timezone=True), nullable=True
            ),
        )

    op.add_column(
        "flight_snapshots",
        sa.Column("origin_airport_code", sa.String(), nullable=True),
    )
    op.add_column(
        "flight_snapshots",
        sa.Column("destination_airport_code", sa.String(), nullable=True),
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
    inspector = sa.inspect(op.get_bind())
    demand_constraints = {
        item["name"]
        for item in inspector.get_unique_constraints(
            "flight_search_demands"
        )
    }
    demand_columns = {
        item["name"]
        for item in inspector.get_columns("flight_search_demands")
    }
    snapshot_columns = {
        item["name"] for item in inspector.get_columns("flight_snapshots")
    }

    op.drop_constraint(
        "uq_platform_price_provider_seller",
        "platform_price_snapshots",
        type_="unique",
    )
    if "destination_airport_code" in snapshot_columns:
        op.drop_column("flight_snapshots", "destination_airport_code")
    if "origin_airport_code" in snapshot_columns:
        op.drop_column("flight_snapshots", "origin_airport_code")
    op.drop_table("collector_nodes")

    op.drop_index(
        "ix_flight_search_demands_due", table_name="flight_search_demands"
    )
    if "uq_flight_search_demand_route_date" in demand_constraints:
        op.drop_constraint(
            "uq_flight_search_demand_route_date",
            "flight_search_demands",
            type_="unique",
        )
    op.drop_constraint(
        "uq_flight_search_demand_hour",
        "flight_search_demands",
        type_="unique",
    )
    op.execute(
        """
        WITH ranked AS (
            SELECT
                origin_code,
                destination_code,
                depart_date,
                first_value(id) OVER current_demand AS keeper_id,
                bool_or(active) OVER route_date AS merged_active,
                max(expires_at) OVER route_date AS merged_expires_at,
                min(next_run_at) OVER route_date AS merged_next_run_at,
                max(last_requested_at)
                    OVER route_date AS merged_last_requested_at,
                max(priority) OVER route_date AS merged_priority,
                first_value(source) OVER priority_source AS merged_source
            FROM flight_search_demands
            WINDOW
                route_date AS (
                    PARTITION BY origin_code, destination_code, depart_date
                ),
                current_demand AS (
                    PARTITION BY origin_code, destination_code, depart_date
                    ORDER BY last_requested_at DESC, demand_hour DESC, id ASC
                ),
                priority_source AS (
                    PARTITION BY origin_code, destination_code, depart_date
                    ORDER BY priority DESC, last_requested_at DESC, id ASC
                )
        ),
        consolidated AS (
            SELECT DISTINCT
                keeper_id,
                merged_active,
                merged_expires_at,
                merged_next_run_at,
                merged_last_requested_at,
                merged_priority,
                merged_source
            FROM ranked
        )
        UPDATE flight_search_demands AS keeper
        SET active = consolidated.merged_active,
            expires_at = consolidated.merged_expires_at,
            next_run_at = consolidated.merged_next_run_at,
            last_requested_at = consolidated.merged_last_requested_at,
            priority = consolidated.merged_priority,
            source = consolidated.merged_source
        FROM consolidated
        WHERE keeper.id = consolidated.keeper_id
        """
    )
    op.execute(
        """
        WITH keepers AS (
            SELECT DISTINCT ON (
                origin_code, destination_code, depart_date
            )
                id,
                origin_code,
                destination_code,
                depart_date
            FROM flight_search_demands
            ORDER BY
                origin_code,
                destination_code,
                depart_date,
                last_requested_at DESC,
                demand_hour DESC,
                id ASC
        )
        DELETE FROM flight_search_demands AS duplicate
        USING keepers
        WHERE duplicate.origin_code = keepers.origin_code
          AND duplicate.destination_code = keepers.destination_code
          AND duplicate.depart_date = keepers.depart_date
          AND duplicate.id <> keepers.id
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
    if "destination_airport_code" in demand_columns:
        op.drop_column(
            "flight_search_demands", "destination_airport_code"
        )
    if "origin_airport_code" in demand_columns:
        op.drop_column("flight_search_demands", "origin_airport_code")
