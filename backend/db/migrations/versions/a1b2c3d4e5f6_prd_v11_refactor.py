"""prd v1.1 refactor: align user_preferences, add sessions and price_alerts

Revision ID: a1b2c3d4e5f6
Revises: 0da3dfe505f8
Create Date: 2026-04-20 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "0da3dfe505f8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    pref_columns = {
        c["name"] for c in inspector.get_columns("user_preferences")
    } if "user_preferences" in tables else set()

    # ── user_preferences: 重命名/新增/删除字段 ───────────────────────────
    if "budget" not in pref_columns:
        op.add_column("user_preferences", sa.Column("budget", sa.Integer(), nullable=True))
    if "frequent_cities" not in pref_columns:
        op.add_column("user_preferences", sa.Column(
            "frequent_cities", postgresql.ARRAY(sa.String()), server_default="{}", nullable=False
        ))
    if "preferred_airlines" not in pref_columns:
        op.add_column("user_preferences", sa.Column(
            "preferred_airlines", postgresql.ARRAY(sa.String()), server_default="{}", nullable=False
        ))
    if "constraints" not in pref_columns:
        op.add_column("user_preferences", sa.Column(
            "constraints", postgresql.ARRAY(sa.String()), server_default="{}", nullable=False
        ))
    if "travel_scenes" not in pref_columns:
        op.add_column("user_preferences", sa.Column(
            "travel_scenes", postgresql.ARRAY(sa.String()), server_default="{}", nullable=False
        ))

    # 迁移旧数据：price_anchor → budget
    if "price_anchor" in pref_columns:
        op.execute("UPDATE user_preferences SET budget = price_anchor WHERE price_anchor IS NOT NULL")
    # 迁移 frequent_destinations → frequent_cities（保留原数据）
    if "frequent_destinations" in pref_columns:
        op.execute(
            "UPDATE user_preferences SET frequent_cities = frequent_destinations "
            "WHERE array_length(frequent_destinations, 1) > 0"
        )

    # 已存在的旧字段保留；ORM 会忽略它们，且可避免修复线上库时破坏历史数据。

    # ── sessions 表 ───────────────────────────────────────────────────────
    if "sessions" not in tables:
        op.create_table(
            "sessions",
            sa.Column("session_id", sa.String(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.Column("last_active_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("session_id"),
        )
        op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)

    # ── price_alerts 表 ───────────────────────────────────────────────────
    if "price_alerts" not in tables:
        op.create_table(
            "price_alerts",
            sa.Column("alert_id", sa.String(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("flight_id", sa.String(), nullable=False),
            sa.Column("origin_city", sa.String(), nullable=False),
            sa.Column("destination_city", sa.String(), nullable=False),
            sa.Column("depart_date", sa.String(), nullable=False),
            sa.Column("current_price", sa.Integer(), nullable=False),
            sa.Column("target_price", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(), server_default="active", nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
            sa.PrimaryKeyConstraint("alert_id"),
        )
        op.create_index(op.f("ix_price_alerts_user_id"), "price_alerts", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_price_alerts_user_id"), table_name="price_alerts")
    op.drop_table("price_alerts")
    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions")
    op.drop_table("sessions")

    op.add_column("user_preferences", sa.Column("price_anchor", sa.Integer(), nullable=True))
    op.add_column("user_preferences", sa.Column(
        "preferred_origins", postgresql.ARRAY(sa.String()), server_default="{}", nullable=False
    ))
    op.add_column("user_preferences", sa.Column(
        "preferred_destinations", postgresql.ARRAY(sa.String()), server_default="{}", nullable=False
    ))
    op.add_column("user_preferences", sa.Column(
        "frequent_destinations", postgresql.ARRAY(sa.String()), server_default="{}", nullable=False
    ))
    op.add_column("user_preferences", sa.Column("travel_window", sa.String(), nullable=True))
    op.add_column("user_preferences", sa.Column("cabin_preference", sa.String(), nullable=True))
    op.add_column("user_preferences", sa.Column(
        "extra", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
    ))
    op.execute("UPDATE user_preferences SET price_anchor = budget WHERE budget IS NOT NULL")
    op.execute(
        "UPDATE user_preferences SET frequent_destinations = frequent_cities "
        "WHERE array_length(frequent_cities, 1) > 0"
    )
    op.drop_column("user_preferences", "budget")
    op.drop_column("user_preferences", "frequent_cities")
    op.drop_column("user_preferences", "preferred_airlines")
    op.drop_column("user_preferences", "constraints")
    op.drop_column("user_preferences", "travel_scenes")
