"""Persistence layer for feature flags."""
from __future__ import annotations

from sqlalchemy import Boolean, Column, Integer, String, select

from backend.infrastructure.db.base import Base, get_session


class FeatureFlag(Base):
    __tablename__ = "feature_flags"
    __table_args__ = {"extend_existing": True}

    name = Column(String, primary_key=True)
    enabled = Column(Boolean, nullable=False, default=False)
    rollout_pct = Column(Integer, nullable=False, default=0)


async def is_enabled(name: str) -> bool:
    async with get_session() as session:
        row = (
            await session.execute(select(FeatureFlag).where(FeatureFlag.name == name))
        ).scalar_one_or_none()
        return bool(row and row.enabled)


async def set_flag(name: str, enabled: bool, rollout_pct: int = 100) -> None:
    async with get_session() as session:
        row = (
            await session.execute(select(FeatureFlag).where(FeatureFlag.name == name))
        ).scalar_one_or_none()
        if row is None:
            session.add(FeatureFlag(name=name, enabled=enabled, rollout_pct=rollout_pct))
        else:
            row.enabled = enabled
            row.rollout_pct = rollout_pct
        await session.commit()
