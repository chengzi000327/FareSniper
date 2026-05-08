from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import Column, DateTime, Integer, String, select
from sqlalchemy.sql import func

from backend.infrastructure.db.base import Base, get_session


class PriceHistoryRow(Base):
    __tablename__ = "price_history"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    origin = Column(String, nullable=False, index=True)
    destination = Column(String, nullable=False, index=True)
    snapshot_at = Column(DateTime(timezone=True), nullable=False, index=True)
    min_price = Column(Integer, nullable=False)


async def write_snapshot(origin: str, destination: str, min_price: int) -> None:
    async with get_session() as s:
        s.add(
            PriceHistoryRow(
                origin=origin,
                destination=destination,
                snapshot_at=datetime.now(timezone.utc),
                min_price=min_price,
            )
        )
        await s.commit()


async def read_history(
    origin: str, destination: str, days: int
) -> list[PriceHistoryRow]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    async with get_session() as s:
        rows = await s.execute(
            select(PriceHistoryRow)
            .where(
                PriceHistoryRow.origin == origin,
                PriceHistoryRow.destination == destination,
                PriceHistoryRow.snapshot_at >= cutoff,
            )
            .order_by(PriceHistoryRow.snapshot_at.asc())
        )
        return list(rows.scalars().all())
