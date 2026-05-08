from __future__ import annotations

from sqlalchemy import Column, DateTime, JSON, String, select
from sqlalchemy.sql import func

from backend.infrastructure.db.base import Base, get_session


class PushSubscription(Base):
    __tablename__ = "push_subscriptions"
    __table_args__ = {"extend_existing": True}

    endpoint = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    subscription = Column(JSON, nullable=False)
    updated_at = Column(DateTime, nullable=False, server_default=func.now())


async def upsert_subscription(user_id: str, subscription: dict) -> None:
    endpoint = subscription["endpoint"]
    async with get_session() as s:
        row = (
            await s.execute(
                select(PushSubscription).where(
                    PushSubscription.endpoint == endpoint
                )
            )
        ).scalar_one_or_none()
        if row is None:
            s.add(
                PushSubscription(
                    user_id=user_id, endpoint=endpoint, subscription=subscription
                )
            )
        else:
            row.user_id = user_id
            row.subscription = subscription
        await s.commit()


async def list_user_subscriptions(user_id: str) -> list[dict]:
    async with get_session() as s:
        rows = (
            await s.execute(
                select(PushSubscription).where(
                    PushSubscription.user_id == user_id
                )
            )
        ).scalars().all()
        return [r.subscription for r in rows]
