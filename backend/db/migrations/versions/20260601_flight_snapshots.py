"""flight snapshots, platform price snapshots, crawl jobs.

Revision ID: 20260601_flight_snapshots
Revises: 20260521_intent_registry
Create Date: 2026-06-01 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20260601_flight_snapshots"
down_revision: Union[str, Sequence[str], None] = "20260521_intent_registry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "flight_snapshots" not in tables:
        op.create_table(
            "flight_snapshots",
            sa.Column("id", sa.String, primary_key=True),
            sa.Column("origin_code", sa.String, nullable=False),
            sa.Column("destination_code", sa.String, nullable=False),
            sa.Column("depart_date", sa.String, nullable=False),
            sa.Column("flight_no", sa.String, nullable=False),
            sa.Column("airline", sa.String, nullable=False, server_default=""),
            sa.Column("dep_time", sa.String, nullable=False, server_default=""),
            sa.Column("arr_time", sa.String, nullable=False, server_default=""),
            sa.Column("duration", sa.String, nullable=False, server_default=""),
            sa.Column("stops", sa.Integer, nullable=False, server_default="0"),
            sa.Column("lowest_price", sa.Integer, nullable=False, server_default="0"),
            sa.Column("history_avg_90d", sa.Integer, nullable=True),
            sa.Column("history_low_90d", sa.Integer, nullable=True),
            sa.Column("crawled_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(
            "ix_flight_snapshots_route",
            "flight_snapshots",
            ["origin_code", "destination_code", "depart_date"],
        )
        op.create_unique_constraint(
            "uq_flight_snapshots_dedup",
            "flight_snapshots",
            ["origin_code", "destination_code", "depart_date", "flight_no", "dep_time"],
        )

    if "platform_price_snapshots" not in tables:
        op.create_table(
            "platform_price_snapshots",
            sa.Column("id", sa.String, primary_key=True),
            sa.Column("flight_snapshot_id", sa.String, sa.ForeignKey("flight_snapshots.id", ondelete="CASCADE"), nullable=False),
            sa.Column("platform", sa.String, nullable=False),
            sa.Column("price", sa.Integer, nullable=False),
            sa.Column("url", sa.Text, nullable=False, server_default=""),
            sa.Column("raw_payload", JSONB, nullable=True),
            sa.Column("crawled_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        )
        op.create_index("ix_platform_price_snapshot_fk", "platform_price_snapshots", ["flight_snapshot_id"])

    if "crawl_jobs" not in tables:
        op.create_table(
            "crawl_jobs",
            sa.Column("job_id", sa.String, primary_key=True),
            sa.Column("route_key", sa.String, nullable=False),
            sa.Column("origin_code", sa.String, nullable=False),
            sa.Column("destination_code", sa.String, nullable=False),
            sa.Column("depart_date", sa.String, nullable=False),
            sa.Column("status", sa.String, nullable=False, server_default="pending"),
            sa.Column("platform_status", JSONB, nullable=False, server_default=sa.text("'{}'")),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_message", sa.Text, nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    for name in ("crawl_jobs", "platform_price_snapshots", "flight_snapshots"):
        if name in tables:
            op.drop_table(name)
