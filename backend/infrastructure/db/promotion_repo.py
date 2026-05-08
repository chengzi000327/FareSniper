from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, DateTime, select
from backend.infrastructure.db.base import Base, get_session


class Promotion(Base):
    __tablename__ = "promotions"
    __table_args__ = {"extend_existing": True}

    platform = Column(String, primary_key=True)
    flight_no = Column(String, primary_key=True)
    date = Column(String, primary_key=True)
    discount_pct = Column(Integer, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)


async def upsert_promotion(
    *, platform: str, flight_no: str, date: str, discount_pct: int, expires_at: str
) -> None:
    ts = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    async with get_session() as s:
        row = (
            await s.execute(
                select(Promotion).where(
                    Promotion.platform == platform,
                    Promotion.flight_no == flight_no,
                    Promotion.date == date,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            s.add(
                Promotion(
                    platform=platform,
                    flight_no=flight_no,
                    date=date,
                    discount_pct=discount_pct,
                    expires_at=ts,
                )
            )
        else:
            row.discount_pct = discount_pct
            row.expires_at = ts
        await s.commit()


async def get_active_promotion(
    platform: str, flight_no: str, date: str
) -> Promotion | None:
    async with get_session() as s:
        row = (
            await s.execute(
                select(Promotion).where(
                    Promotion.platform == platform,
                    Promotion.flight_no == flight_no,
                    Promotion.date == date,
                    Promotion.expires_at > datetime.now(timezone.utc),
                )
            )
        ).scalar_one_or_none()
        return row
