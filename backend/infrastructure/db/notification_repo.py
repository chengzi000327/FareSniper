from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Integer,
    String,
    UniqueConstraint,
    select,
)
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.sql import func

from backend.infrastructure.db.base import Base, get_session


class AlertSubscription(Base):
    __tablename__ = "alert_subscriptions"
    __table_args__ = (
        UniqueConstraint("alert_id", "channel", name="uq_alert_subscription_channel"),
        {"extend_existing": True},
    )

    id = Column(String, primary_key=True)
    alert_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    channel = Column(String, nullable=False)
    template_id = Column(String, nullable=True)
    status = Column(String, nullable=False, server_default="accepted")
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    consumed_at = Column(DateTime, nullable=True)


class NotificationOutbox(Base):
    __tablename__ = "notification_outbox"
    __table_args__ = (
        UniqueConstraint("event_key", name="uq_notification_event_key"),
        {"extend_existing": True},
    )

    id = Column(String, primary_key=True)
    event_key = Column(String, nullable=False)
    alert_id = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    channel = Column(String, nullable=False)
    payload = Column(JSON, nullable=False)
    status = Column(String, nullable=False, server_default="pending")
    attempts = Column(Integer, nullable=False, server_default="0")
    next_attempt_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    lease_until = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(String, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    sent_at = Column(DateTime(timezone=True), nullable=True)


async def upsert_alert_subscription(
    *,
    alert_id: str,
    user_id: str,
    channel: str,
    template_id: str | None = None,
) -> AlertSubscription:
    async with get_session() as session:
        row = (
            await session.execute(
                select(AlertSubscription).where(
                    AlertSubscription.alert_id == alert_id,
                    AlertSubscription.channel == channel,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            row = AlertSubscription(
                id=f"sub_{uuid.uuid4().hex[:16]}",
                alert_id=alert_id,
                user_id=user_id,
                channel=channel,
                template_id=template_id,
                status="accepted",
            )
            session.add(row)
        else:
            row.template_id = template_id
            row.status = "accepted"
            row.consumed_at = None
        await session.commit()
        return row


async def list_alert_subscriptions(alert_id: str) -> list[AlertSubscription]:
    async with get_session() as session:
        return list(
            (
                await session.execute(
                    select(AlertSubscription).where(
                        AlertSubscription.alert_id == alert_id,
                        AlertSubscription.status == "accepted",
                    )
                )
            )
            .scalars()
            .all()
        )


async def mark_subscription_consumed(subscription_id: str) -> None:
    async with get_session() as session:
        row = await session.get(AlertSubscription, subscription_id)
        if row is not None:
            row.status = "consumed"
            row.consumed_at = datetime.now(timezone.utc)
            await session.commit()


async def mark_subscription_invalid(subscription_id: str) -> None:
    async with get_session() as session:
        row = await session.get(AlertSubscription, subscription_id)
        if row is not None:
            row.status = "invalid"
            await session.commit()


async def enqueue_notification(
    *,
    event_key: str,
    alert_id: str,
    user_id: str,
    channel: str,
    payload: dict[str, Any],
) -> NotificationOutbox:
    async with get_session() as session:
        notification_id = f"notification_{uuid.uuid4().hex[:16]}"
        stmt = (
            pg_insert(NotificationOutbox.__table__)
            .values(
                id=notification_id,
                event_key=event_key,
                alert_id=alert_id,
                user_id=user_id,
                channel=channel,
                payload=payload,
                status="pending",
            )
            .on_conflict_do_nothing(index_elements=["event_key"])
            .returning(NotificationOutbox.id)
        )
        inserted_id = (await session.execute(stmt)).scalar_one_or_none()
        row_filter = (
            NotificationOutbox.id == inserted_id
            if inserted_id
            else NotificationOutbox.event_key == event_key
        )
        row = (
            await session.execute(select(NotificationOutbox).where(row_filter))
        ).scalar_one()
        await session.commit()
        return row


async def claim_due_notifications(
    *, limit: int = 50, lease_seconds: int = 60
) -> list[NotificationOutbox]:
    now = datetime.now(timezone.utc)
    async with get_session() as session:
        rows = list(
            (
                await session.execute(
                    select(NotificationOutbox)
                    .where(
                        NotificationOutbox.next_attempt_at <= now,
                        (
                            NotificationOutbox.status.in_(["pending", "retry"])
                            | (
                                (NotificationOutbox.status == "sending")
                                & (NotificationOutbox.lease_until < now)
                            )
                        ),
                    )
                    .order_by(NotificationOutbox.created_at)
                    .limit(limit)
                    .with_for_update(skip_locked=True)
                )
            )
            .scalars()
            .all()
        )
        lease_until = now + timedelta(seconds=lease_seconds)
        for row in rows:
            row.status = "sending"
            row.attempts = int(row.attempts or 0) + 1
            row.lease_until = lease_until
        await session.commit()
        return rows


async def mark_notification_sent(notification_id: str) -> None:
    async with get_session() as session:
        row = await session.get(NotificationOutbox, notification_id)
        if row is not None:
            row.status = "sent"
            row.sent_at = datetime.now(timezone.utc)
            row.lease_until = None
            row.last_error = None
            await session.commit()


async def mark_notification_retry(
    notification_id: str, error: str, *, max_attempts: int = 5
) -> None:
    async with get_session() as session:
        row = await session.get(NotificationOutbox, notification_id)
        if row is None:
            return
        attempts = int(row.attempts or 0)
        row.status = "failed" if attempts >= max_attempts else "retry"
        row.last_error = error[:1000]
        row.lease_until = None
        row.next_attempt_at = datetime.now(timezone.utc) + timedelta(
            seconds=min(60 * (2 ** max(attempts - 1, 0)), 3600)
        )
        await session.commit()


async def mark_notification_failed(notification_id: str, error: str) -> None:
    async with get_session() as session:
        row = await session.get(NotificationOutbox, notification_id)
        if row is not None:
            row.status = "failed"
            row.last_error = error[:1000]
            row.lease_until = None
            await session.commit()
