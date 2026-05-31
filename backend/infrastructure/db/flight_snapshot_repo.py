from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import (
    Column, DateTime, ForeignKey, Integer, String, Text, delete, select,
)
from sqlalchemy.dialects.postgresql import JSONB

from backend.infrastructure.db.base import Base, get_session

CACHE_TTL = timedelta(hours=1)


class FlightSnapshot(Base):
    __tablename__ = "flight_snapshots"
    __table_args__ = {"extend_existing": True}

    id = Column(String, primary_key=True)
    origin_code = Column(String, nullable=False)
    destination_code = Column(String, nullable=False)
    depart_date = Column(String, nullable=False)
    flight_no = Column(String, nullable=False)
    airline = Column(String, nullable=False, default="")
    dep_time = Column(String, nullable=False, default="")
    arr_time = Column(String, nullable=False, default="")
    duration = Column(String, nullable=False, default="")
    stops = Column(Integer, nullable=False, default=0)
    lowest_price = Column(Integer, nullable=False, default=0)
    history_avg_90d = Column(Integer, nullable=True)
    history_low_90d = Column(Integer, nullable=True)
    crawled_at = Column(DateTime(timezone=True), nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)


class PlatformPriceSnapshot(Base):
    __tablename__ = "platform_price_snapshots"
    __table_args__ = {"extend_existing": True}

    id = Column(String, primary_key=True)
    flight_snapshot_id = Column(String, ForeignKey("flight_snapshots.id", ondelete="CASCADE"), nullable=False)
    platform = Column(String, nullable=False)
    price = Column(Integer, nullable=False)
    url = Column(Text, nullable=False, default="")
    raw_payload = Column(JSONB, nullable=True)
    crawled_at = Column(DateTime(timezone=True), nullable=False)


def _snapshot_id(f: dict[str, Any]) -> str:
    raw = f"{f['origin_code']}|{f['destination_code']}|{f['depart_date']}|{f['flight_no']}|{f['dep_time']}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]


async def upsert_flights(flights: list[dict[str, Any]]) -> None:
    now = datetime.now(timezone.utc)
    async with get_session() as s:
        for f in flights:
            sid = _snapshot_id(f)
            await s.execute(delete(PlatformPriceSnapshot).where(PlatformPriceSnapshot.flight_snapshot_id == sid))
            existing = await s.get(FlightSnapshot, sid)
            if existing is None:
                existing = FlightSnapshot(id=sid)
                s.add(existing)
            existing.origin_code = f["origin_code"]
            existing.destination_code = f["destination_code"]
            existing.depart_date = f["depart_date"]
            existing.flight_no = f["flight_no"]
            existing.airline = f.get("airline", "")
            existing.dep_time = f.get("dep_time", "")
            existing.arr_time = f.get("arr_time", "")
            existing.duration = f.get("duration", "")
            existing.stops = int(f.get("stops", 0))
            existing.lowest_price = int(f.get("lowest_price", 0))
            existing.history_avg_90d = f.get("history_avg_90d")
            existing.history_low_90d = f.get("history_low_90d")
            existing.crawled_at = now
            existing.expires_at = now + CACHE_TTL
            for idx, p in enumerate(f.get("prices", [])):
                s.add(PlatformPriceSnapshot(
                    id=f"{sid}-{idx}",
                    flight_snapshot_id=sid,
                    platform=p["platform"],
                    price=int(p["price"]),
                    url=p.get("url", ""),
                    raw_payload=p.get("raw_payload"),
                    crawled_at=now,
                ))
        await s.commit()


async def read_deals(*, origin_code: str, destination_code: str, depart_date: str) -> list[dict[str, Any]]:
    async with get_session() as s:
        snaps = (await s.execute(
            select(FlightSnapshot).where(
                FlightSnapshot.origin_code == origin_code,
                FlightSnapshot.destination_code == destination_code,
                FlightSnapshot.depart_date == depart_date,
            ).order_by(FlightSnapshot.lowest_price.asc())
        )).scalars().all()
        if not snaps:
            return []
        deals: list[dict[str, Any]] = []
        for snap in snaps:
            prices = (await s.execute(
                select(PlatformPriceSnapshot)
                .where(PlatformPriceSnapshot.flight_snapshot_id == snap.id)
                .order_by(PlatformPriceSnapshot.price.asc())
            )).scalars().all()
            price_items = [
                {"platform": p.platform, "price": p.price, "url": p.url, "lowest": p.price == snap.lowest_price}
                for p in prices
            ]
            deals.append({
                "flight_no": snap.flight_no, "airline": snap.airline,
                "origin_code": snap.origin_code, "destination_code": snap.destination_code,
                "depart_date": snap.depart_date, "dep_time": snap.dep_time, "arr_time": snap.arr_time,
                "duration": snap.duration, "stops": snap.stops, "lowest_price": snap.lowest_price,
                "history_avg_90d": snap.history_avg_90d, "history_low_90d": snap.history_low_90d,
                "prices": price_items,
                "data_freshness": "stale" if (snap.expires_at and snap.expires_at < datetime.now(timezone.utc)) else "fresh",
            })
        return deals
