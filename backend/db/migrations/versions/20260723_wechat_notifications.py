"""add wechat identity and reliable notification outbox.

Revision ID: 20260723_wechat_notifications
Revises: 20260719_offer_fee_details
Create Date: 2026-07-23 00:00:00.000000
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260723_wechat_notifications"
down_revision: Union[str, Sequence[str], None] = "20260719_offer_fee_details"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(inspector, table: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "alerts" in tables:
        columns = _columns(inspector, "alerts")
        additions = [
            ("current_price", sa.Integer(), True, None),
            ("currency", sa.String(), False, "CNY"),
            ("latest_price", sa.Integer(), True, None),
            ("latest_provider", sa.String(), True, None),
            ("latest_quote_at", sa.DateTime(timezone=True), True, None),
            ("notification_status", sa.String(), False, "not_requested"),
            ("updated_at", sa.DateTime(timezone=True), False, None),
        ]
        for name, type_, nullable, default in additions:
            if name in columns:
                continue
            server_default = (
                sa.text("now()")
                if name == "updated_at"
                else (sa.text(f"'{default}'") if default else None)
            )
            op.add_column(
                "alerts",
                sa.Column(
                    name,
                    type_,
                    nullable=nullable,
                    server_default=server_default,
                ),
            )

    if "price_alerts" in tables and "alerts" in tables:
        op.execute(sa.text("""
                INSERT INTO alerts (
                    id, user_id, origin, destination, depart_date,
                    target_price, current_price, currency, latest_price,
                    notification_status, status, created_at, updated_at
                )
                SELECT
                    alert_id, user_id, origin_city, destination_city,
                    depart_date, target_price, current_price, 'CNY',
                    current_price, 'not_requested', status, created_at,
                    created_at
                FROM price_alerts
                ON CONFLICT (id) DO NOTHING
                """))
        indexes = {item["name"] for item in inspector.get_indexes("price_alerts")}
        if "ix_price_alerts_user_id" in indexes:
            op.drop_index("ix_price_alerts_user_id", table_name="price_alerts")
        op.drop_table("price_alerts")

    if "wechat_accounts" not in tables:
        op.create_table(
            "wechat_accounts",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("app_id", sa.String(), nullable=False),
            sa.Column("open_id", sa.String(), nullable=False),
            sa.Column("union_id", sa.String(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("app_id", "open_id", name="uq_wechat_app_openid"),
        )
        op.create_index(
            "ix_wechat_accounts_user_id",
            "wechat_accounts",
            ["user_id"],
        )

    if "alert_subscriptions" not in tables:
        op.create_table(
            "alert_subscriptions",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("alert_id", sa.String(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("channel", sa.String(), nullable=False),
            sa.Column("template_id", sa.String(), nullable=True),
            sa.Column(
                "status",
                sa.String(),
                nullable=False,
                server_default="accepted",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("consumed_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "alert_id",
                "channel",
                name="uq_alert_subscription_channel",
            ),
        )
        op.create_index(
            "ix_alert_subscriptions_alert_id",
            "alert_subscriptions",
            ["alert_id"],
        )
        op.create_index(
            "ix_alert_subscriptions_user_id",
            "alert_subscriptions",
            ["user_id"],
        )

    if "notification_outbox" not in tables:
        op.create_table(
            "notification_outbox",
            sa.Column("id", sa.String(), nullable=False),
            sa.Column("event_key", sa.String(), nullable=False),
            sa.Column("alert_id", sa.String(), nullable=False),
            sa.Column("user_id", sa.String(), nullable=False),
            sa.Column("channel", sa.String(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column(
                "status",
                sa.String(),
                nullable=False,
                server_default="pending",
            ),
            sa.Column(
                "attempts",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "next_attempt_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
            sa.Column("last_error", sa.String(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("event_key", name="uq_notification_event_key"),
        )
        op.create_index(
            "ix_notification_outbox_alert_id",
            "notification_outbox",
            ["alert_id"],
        )
        op.create_index(
            "ix_notification_outbox_user_id",
            "notification_outbox",
            ["user_id"],
        )


def downgrade() -> None:
    op.drop_table("notification_outbox")
    op.drop_table("alert_subscriptions")
    op.drop_table("wechat_accounts")
    for column in [
        "updated_at",
        "notification_status",
        "latest_quote_at",
        "latest_provider",
        "latest_price",
        "currency",
        "current_price",
    ]:
        op.drop_column("alerts", column)
