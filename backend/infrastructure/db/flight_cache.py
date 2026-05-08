from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, JSON, String, select
from sqlalchemy.sql import func

from backend.infrastructure.db.base import Base, get_session


class FlightCache(Base):
    __tablename__ = "flight_cache"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True)
    origin = Column(String, nullable=False, index=True)
    destination = Column(String, nullable=False, index=True)
    depart_date = Column(String, nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    fetched_at = Column(DateTime, nullable=False, server_default=func.now())


async def write_cached_deals(
    *, origin: str, destination: str, depart_date: str, deals: list[dict]
) -> None:
    async with get_session() as s:
        s.add(
            FlightCache(
                origin=origin,
                destination=destination,
                depart_date=depart_date,
                payload={"deals": deals},
            )
        )
        await s.commit()


async def read_cached_deals(
    *, origin: str, destination: str, depart_date: str
) -> list[dict]:
    async with get_session() as s:
        stmt = (
            select(FlightCache)
            .where(
                FlightCache.origin == origin,
                FlightCache.destination == destination,
                FlightCache.depart_date == depart_date,
            )
            .order_by(FlightCache.fetched_at.desc())
            .limit(1)
        )
        row = (await s.execute(stmt)).scalar_one_or_none()
        return row.payload["deals"] if row else []
