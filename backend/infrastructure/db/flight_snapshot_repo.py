from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    delete,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB, insert as pg_insert

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
    raw = (
        f"{f['origin_code']}|{f['destination_code']}|{f['depart_date']}|"
        f"{f['flight_no']}|{f.get('dep_time', '')}"
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:24]


def _advisory_lock_key(snapshot_id: str) -> int:
    return int(hashlib.sha1(snapshot_id.encode("utf-8")).hexdigest()[:15], 16)


async def upsert_flights(flights: list[dict[str, Any]]) -> None:
    now = datetime.now(timezone.utc)
    async with get_session() as s:
        for f in flights:
            sid = _snapshot_id(f)
            await s.execute(select(func.pg_advisory_xact_lock(_advisory_lock_key(sid))))
            values = {
                "id": sid,
                "origin_code": f["origin_code"],
                "destination_code": f["destination_code"],
                "depart_date": f["depart_date"],
                "flight_no": f["flight_no"],
                "airline": f.get("airline", ""),
                "dep_time": f.get("dep_time", ""),
                "arr_time": f.get("arr_time", ""),
                "duration": f.get("duration", ""),
                "stops": int(f.get("stops", 0)),
                "lowest_price": int(f.get("lowest_price", 0)),
                "history_avg_90d": f.get("history_avg_90d"),
                "history_low_90d": f.get("history_low_90d"),
                "crawled_at": now,
                "expires_at": now + CACHE_TTL,
            }
            stmt = pg_insert(FlightSnapshot.__table__).values(**values)
            await s.execute(
                stmt.on_conflict_do_update(
                    index_elements=[FlightSnapshot.id],
                    set_={k: v for k, v in values.items() if k != "id"},
                )
            )
            await s.execute(
                delete(PlatformPriceSnapshot).where(
                    PlatformPriceSnapshot.flight_snapshot_id == sid
                )
            )
            price_rows = [
                {
                    "id": f"{sid}-{idx}",
                    "flight_snapshot_id": sid,
                    "platform": p["platform"],
                    "price": int(p["price"]),
                    "url": p.get("url", ""),
                    "raw_payload": p.get("raw_payload"),
                    "crawled_at": now,
                }
                for idx, p in enumerate(f.get("prices", []))
            ]
            if price_rows:
                await s.execute(
                    pg_insert(PlatformPriceSnapshot.__table__).values(price_rows)
                )
        await s.commit()


async def read_deals_latest(*, origin_code: str, destination_code: str) -> list[dict[str, Any]]:
    """兜底:返回该路线库里最新 ``depart_date`` 的全部 deals。

    用于推荐瀑布流——当未来 N 天没有任何快照时,退回到该路线已抓到的
    最新一批数据,确保卡片不至于因日期错位而整体落空。
    """
    async with get_session() as s:
        latest = (await s.execute(
            select(func.max(FlightSnapshot.depart_date)).where(
                FlightSnapshot.origin_code == origin_code,
                FlightSnapshot.destination_code == destination_code,
            )
        )).scalar_one_or_none()
    if not latest:
        return []
    return await read_deals(
        origin_code=origin_code, destination_code=destination_code, depart_date=latest
    )


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
