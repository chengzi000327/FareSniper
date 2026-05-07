"""Persistence layer for analytics events."""
from __future__ import annotations

from typing import Union

from sqlalchemy import Column, DateTime, Integer, JSON, String, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.analytics.events import EventName
from backend.infrastructure.db.base import Base, get_session


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    event_name = Column(String, nullable=False, index=True)
    user_id = Column(String, nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    # The migration column is TIMESTAMP WITHOUT TIME ZONE, so we let PG
    # populate created_at via ``server_default=func.now()`` instead of
    # supplying a tz-aware Python default that asyncpg would reject.
    created_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        index=True,
    )


async def insert_event(name: str, user_id: str, payload: dict) -> None:
    async with get_session() as session:  # type: AsyncSession
        session.add(AnalyticsEvent(event_name=name, user_id=user_id, payload=payload))
        await session.commit()


async def count_events(name: Union[EventName, str], user_id: str) -> int:
    event_value = name.value if isinstance(name, EventName) else name
    async with get_session() as session:  # type: AsyncSession
        stmt = (
            select(func.count())
            .select_from(AnalyticsEvent)
            .where(AnalyticsEvent.event_name == event_value)
            .where(AnalyticsEvent.user_id == user_id)
        )
        return (await session.execute(stmt)).scalar_one()
