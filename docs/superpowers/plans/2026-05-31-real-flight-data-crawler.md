# 真实航班数据与每小时爬虫缓存 实施计划（Plan 2/4）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**前置依赖：** Plan 1（ReAct 主链路）已落地——`search_flights` 工具已是查价唯一入口。

**Goal:** 落地 PRD §5.2.5 / §9.3 的真实数据层：新增 `flight_snapshots / platform_price_snapshots / crawl_jobs` 三张表，提供读模型 `FlightCacheRepository`，把每小时爬虫产出 upsert 入库，并让 `search_flights` 工具改读三表（命中返回归一化航班列表，未命中返回空数组并标记数据新鲜度）。

**Architecture:** 后台 `scrape_all_routes`（已被 `workers/scheduler.py` 每小时触发）改造为：生成 `crawl_jobs` → 调多平台爬虫 → 归一化 → 按 `flight_no+dep_time+depart_date` 聚合写 `flight_snapshots`，各平台价格写 `platform_price_snapshots`。用户查询链路只读 `FlightCacheRepository.read_deals()`，按 `origin_code+destination_code+depart_date` 命中，组装含 `prices[]` 的 deal dict。

**Tech Stack:** Alembic / SQLAlchemy async / APScheduler / pytest（seeded_pg 走 `TEST_DATABASE_URL`，遵循 [[feedback_test_db_strategy]]）。

---

## File Structure

| 文件 | 责任 | 动作 |
|------|------|------|
| `backend/db/migrations/versions/20260601_flight_snapshots.py` | 建三表 + 索引 | Create |
| `backend/infrastructure/db/flight_snapshot_repo.py` | ORM 模型 + upsert + 读模型 | Create |
| `backend/infrastructure/db/crawl_job_repo.py` | crawl_jobs 模型 + 状态写入 | Create |
| `backend/data_sources/normalizer.py` | 爬虫原始字段 → 业务字段归一化 | Create |
| `backend/infrastructure/scrapers/multi_platform.py` | `scrape_all_routes` 改为落库 | Modify |
| `backend/application/graph/tools/search_flights.py` | 改读 FlightCacheRepository | Modify |
| `backend/utils/airport_codes.py` | 复用 `city_to_code`（已存在，确认覆盖高频航线） | Verify |
| `backend/tests/infra/test_flight_snapshot_repo.py` | 新增 | Create |
| `backend/tests/services/test_normalizer.py` | 新增 | Create |
| `backend/tests/graph/tools/test_search_flights.py` | 改为断言读三表 | Modify |

---

## Task 1: 三表 Alembic 迁移

**Files:**
- Create: `backend/db/migrations/versions/20260601_flight_snapshots.py`
- Test: `backend/tests/test_alembic_head.py`（已存在，验证 head 单一）

- [ ] **Step 1: 写迁移文件**

```python
"""flight snapshots, platform price snapshots, crawl jobs.

Revision ID: 20260601_flight_snapshots
Revises: 20260521_intent_registry
Create Date: 2026-06-01 00:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "20260601_flight_snapshots"
down_revision: Union[str, Sequence[str], None] = "20260521_intent_registry"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "flight_snapshots" not in tables:
        op.create_table(
            "flight_snapshots",
            sa.Column("id", sa.String, primary_key=True),
            sa.Column("origin_code", sa.String, nullable=False),
            sa.Column("destination_code", sa.String, nullable=False),
            sa.Column("depart_date", sa.String, nullable=False),
            sa.Column("flight_no", sa.String, nullable=False),
            sa.Column("airline", sa.String, nullable=False, server_default=""),
            sa.Column("dep_time", sa.String, nullable=False, server_default=""),
            sa.Column("arr_time", sa.String, nullable=False, server_default=""),
            sa.Column("duration", sa.String, nullable=False, server_default=""),
            sa.Column("stops", sa.Integer, nullable=False, server_default="0"),
            sa.Column("lowest_price", sa.Integer, nullable=False, server_default="0"),
            sa.Column("history_avg_90d", sa.Integer, nullable=True),
            sa.Column("history_low_90d", sa.Integer, nullable=True),
            sa.Column("crawled_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        )
        op.create_index(
            "ix_flight_snapshots_route",
            "flight_snapshots",
            ["origin_code", "destination_code", "depart_date"],
        )
        op.create_unique_constraint(
            "uq_flight_snapshots_dedup",
            "flight_snapshots",
            ["origin_code", "destination_code", "depart_date", "flight_no", "dep_time"],
        )

    if "platform_price_snapshots" not in tables:
        op.create_table(
            "platform_price_snapshots",
            sa.Column("id", sa.String, primary_key=True),
            sa.Column("flight_snapshot_id", sa.String, sa.ForeignKey("flight_snapshots.id", ondelete="CASCADE"), nullable=False),
            sa.Column("platform", sa.String, nullable=False),
            sa.Column("price", sa.Integer, nullable=False),
            sa.Column("url", sa.Text, nullable=False, server_default=""),
            sa.Column("raw_payload", JSONB, nullable=True),
            sa.Column("crawled_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_platform_price_snapshot_fk", "platform_price_snapshots", ["flight_snapshot_id"])

    if "crawl_jobs" not in tables:
        op.create_table(
            "crawl_jobs",
            sa.Column("job_id", sa.String, primary_key=True),
            sa.Column("route_key", sa.String, nullable=False),
            sa.Column("origin_code", sa.String, nullable=False),
            sa.Column("destination_code", sa.String, nullable=False),
            sa.Column("depart_date", sa.String, nullable=False),
            sa.Column("status", sa.String, nullable=False, server_default="pending"),
            sa.Column("platform_status", JSONB, nullable=False, server_default=sa.text("'{}'")),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_message", sa.Text, nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    for name in ("crawl_jobs", "platform_price_snapshots", "flight_snapshots"):
        if name in tables:
            op.drop_table(name)
```

- [ ] **Step 2: 验证 head 单一、可升级**

Run: `pytest backend/tests/test_alembic_head.py backend/tests/test_alembic_runs_in_pytest.py -v`
Expected: PASS（head=`20260601_flight_snapshots`）

- [ ] **Step 3: 提交**

```bash
git add backend/db/migrations/versions/20260601_flight_snapshots.py
git commit -m "feat(db): add flight_snapshots/platform_price_snapshots/crawl_jobs tables"
```

---

## Task 2: 归一化器（爬虫原始字段 → 业务字段）

**Files:**
- Create: `backend/data_sources/normalizer.py`
- Test: `backend/tests/services/test_normalizer.py`

> 爬虫原始字段（PRD §9.3）：`flight_number, airline, dep_city, arr_city, dep_time, arr_time, duration, transfer_count, price, discount_rate, date, platform`。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/services/test_normalizer.py
from backend.data_sources.normalizer import normalize_raw_rows


def test_aggregates_same_flight_across_platforms():
    rows = [
        {"flight_number": "HU7833", "airline": "海南航空", "dep_city": "北京", "arr_city": "三亚",
         "dep_time": "09:30", "arr_time": "14:20", "duration": "4h50m", "transfer_count": 0,
         "price": 410, "date": "2026-05-01", "platform": "飞猪"},
        {"flight_number": "HU7833", "airline": "海南航空", "dep_city": "北京", "arr_city": "三亚",
         "dep_time": "09:30", "arr_time": "14:20", "duration": "4h50m", "transfer_count": 0,
         "price": 389, "date": "2026-05-01", "platform": "携程"},
    ]
    out = normalize_raw_rows(rows)
    assert len(out) == 1
    f = out[0]
    assert f["flight_no"] == "HU7833"
    assert f["stops"] == 0
    assert f["lowest_price"] == 389
    assert {p["platform"] for p in f["prices"]} == {"飞猪", "携程"}
    assert any(p["lowest"] for p in f["prices"] if p["platform"] == "携程")
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest backend/tests/services/test_normalizer.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 normalizer.py**

```python
from __future__ import annotations

from typing import Any

from backend.utils.airport_codes import city_to_code


def _key(row: dict[str, Any]) -> tuple:
    return (row.get("flight_number", ""), row.get("dep_time", ""), row.get("date", ""))


def normalize_raw_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """把多平台原始抓取行聚合为业务航班结构（同航班按 flight_no+dep_time+date 聚合）。"""
    grouped: dict[tuple, dict[str, Any]] = {}
    for row in rows:
        price = row.get("price")
        if not isinstance(price, (int, float)) or price <= 0:
            continue  # 丢弃异常价格，不影响同航班其它平台
        key = _key(row)
        flight = grouped.get(key)
        if flight is None:
            flight = {
                "flight_no": row.get("flight_number", ""),
                "airline": row.get("airline", ""),
                "origin_city": row.get("dep_city", ""),
                "destination_city": row.get("arr_city", ""),
                "origin_code": city_to_code(row.get("dep_city", "")),
                "destination_code": city_to_code(row.get("arr_city", "")),
                "depart_date": row.get("date", ""),
                "dep_time": row.get("dep_time", ""),
                "arr_time": row.get("arr_time", ""),
                "duration": row.get("duration", ""),
                "stops": int(row.get("transfer_count", 0) or 0),
                "prices": [],
                "history_avg_90d": None,
                "history_low_90d": None,
            }
            grouped[key] = flight
        flight["prices"].append(
            {"platform": row.get("platform", ""), "price": int(price), "url": row.get("url", "")}
        )

    out: list[dict[str, Any]] = []
    for flight in grouped.values():
        flight["prices"].sort(key=lambda p: p["price"])
        lowest = flight["prices"][0]["price"]
        flight["lowest_price"] = lowest
        for p in flight["prices"]:
            p["lowest"] = p["price"] == lowest
        out.append(flight)
    return out
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest backend/tests/services/test_normalizer.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/data_sources/normalizer.py backend/tests/services/test_normalizer.py
git commit -m "feat(data): normalize multi-platform raw rows into aggregated flights"
```

---

## Task 3: FlightCacheRepository（upsert + 读模型）

**Files:**
- Create: `backend/infrastructure/db/flight_snapshot_repo.py`
- Test: `backend/tests/infra/test_flight_snapshot_repo.py`

- [ ] **Step 1: 写失败测试（seeded_pg → TEST_DATABASE_URL）**

```python
# backend/tests/infra/test_flight_snapshot_repo.py
import pytest

from backend.infrastructure.db.flight_snapshot_repo import upsert_flights, read_deals


@pytest.mark.asyncio
async def test_upsert_then_read(seeded_pg):
    flights = [{
        "flight_no": "MU5106", "airline": "东方航空",
        "origin_code": "BJS", "destination_code": "SHA", "depart_date": "2026-05-01",
        "dep_time": "08:00", "arr_time": "10:00", "duration": "2h00m", "stops": 0,
        "lowest_price": 280, "history_avg_90d": 420, "history_low_90d": 240,
        "prices": [
            {"platform": "携程", "price": 280, "lowest": True, "url": "ctrip://x"},
            {"platform": "去哪儿", "price": 299, "lowest": False, "url": "qunar://x"},
        ],
    }]
    await upsert_flights(flights)
    deals = await read_deals(origin_code="BJS", destination_code="SHA", depart_date="2026-05-01")
    assert len(deals) == 1
    assert deals[0]["flight_no"] == "MU5106"
    assert deals[0]["lowest_price"] == 280
    assert len(deals[0]["prices"]) == 2


@pytest.mark.asyncio
async def test_read_miss_returns_empty(seeded_pg):
    assert await read_deals(origin_code="BJS", destination_code="XIY", depart_date="2026-05-01") == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest backend/tests/infra/test_flight_snapshot_repo.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 flight_snapshot_repo.py**

```python
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
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest backend/tests/infra/test_flight_snapshot_repo.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/infrastructure/db/flight_snapshot_repo.py backend/tests/infra/test_flight_snapshot_repo.py
git commit -m "feat(db): FlightCacheRepository upsert + read_deals over snapshot tables"
```

---

## Task 4: search_flights 工具改读三表

**Files:**
- Modify: `backend/application/graph/tools/search_flights.py:1-53`
- Test: `backend/tests/graph/tools/test_search_flights.py`

- [ ] **Step 1: 改写测试，断言读取快照仓储**

```python
# backend/tests/graph/tools/test_search_flights.py
import pytest

import backend.application.graph.tools.search_flights as sf


@pytest.mark.asyncio
async def test_search_reads_snapshot_repo(monkeypatch):
    async def fake_read(*, origin_code, destination_code, depart_date):
        return [{"flight_no": "MU5106", "lowest_price": 280, "prices": []}]

    monkeypatch.setattr(sf, "read_deals", fake_read)
    out = await sf.search_flights.ainvoke({"origin": "北京", "destination": "上海", "depart_date": "2026-05-01"})
    assert out["source"] == "cache"
    assert out["deals"][0]["flight_no"] == "MU5106"


@pytest.mark.asyncio
async def test_search_mock_fallback_when_empty(monkeypatch):
    async def empty_read(*, origin_code, destination_code, depart_date):
        return []

    monkeypatch.setattr(sf, "read_deals", empty_read)
    monkeypatch.setattr(sf.settings, "enable_mock_fallback", True)
    out = await sf.search_flights.ainvoke({"origin": "北京", "destination": "上海", "depart_date": "2026-05-01"})
    assert out["source"] == "mock_fallback"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest backend/tests/graph/tools/test_search_flights.py -v`
Expected: FAIL（当前 import 的是 `flight_cache.read_cached_deals`，无 `read_deals`）

- [ ] **Step 3: 重写 search_flights.py**

```python
from __future__ import annotations

import logging

from langchain_core.tools import tool

from backend.config import settings
from backend.data_sources.mock_flights import get_mock_flights
from backend.infrastructure.db.flight_snapshot_repo import read_deals
from backend.utils.airport_codes import city_to_code

logger = logging.getLogger("faresniper.graph.tools.search_flights")


@tool
async def search_flights(origin: str, destination: str, depart_date: str) -> dict:
    """读取航班价格缓存（快照表）。命中返回归一化航班列表，未命中按配置回退 mock。"""
    try:
        deals = await read_deals(
            origin_code=city_to_code(origin),
            destination_code=city_to_code(destination),
            depart_date=depart_date,
        )
    except Exception:
        logger.exception(
            "flight_snapshot_read_failed origin=%s destination=%s depart_date=%s",
            origin, destination, depart_date,
        )
        deals = []

    if deals:
        return {"deals": deals, "source": "cache"}

    if settings.enable_mock_fallback:
        return {"deals": get_mock_flights(origin, destination, depart_date), "source": "mock_fallback"}
    return {"deals": [], "source": "empty"}
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest backend/tests/graph/tools/test_search_flights.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/application/graph/tools/search_flights.py backend/tests/graph/tools/test_search_flights.py
git commit -m "feat(tool): search_flights reads from snapshot cache repository"
```

---

## Task 5: 爬虫落库（scrape_all_routes → crawl_jobs + 快照 upsert）

**Files:**
- Modify: `backend/infrastructure/scrapers/multi_platform.py:30-50`
- Create: `backend/infrastructure/db/crawl_job_repo.py`
- Test: `backend/tests/scrapers/test_multi_platform.py`

- [ ] **Step 1: crawl_job_repo.py（状态写入）**

```python
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB

from backend.infrastructure.db.base import Base, get_session


class CrawlJob(Base):
    __tablename__ = "crawl_jobs"
    __table_args__ = {"extend_existing": True}

    job_id = Column(String, primary_key=True)
    route_key = Column(String, nullable=False)
    origin_code = Column(String, nullable=False)
    destination_code = Column(String, nullable=False)
    depart_date = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending")
    platform_status = Column(JSONB, nullable=False, default=dict)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)


async def record_job(
    *, origin_code: str, destination_code: str, depart_date: str,
    status: str, platform_status: dict[str, Any], error_message: str | None = None,
) -> None:
    async with get_session() as s:
        s.add(CrawlJob(
            job_id=uuid.uuid4().hex,
            route_key=f"{origin_code}-{destination_code}",
            origin_code=origin_code, destination_code=destination_code, depart_date=depart_date,
            status=status, platform_status=platform_status,
            started_at=datetime.now(timezone.utc), finished_at=datetime.now(timezone.utc),
            error_message=error_message,
        ))
        await s.commit()
```

- [ ] **Step 2: 写失败测试（聚合落库）**

```python
# 追加到 backend/tests/scrapers/test_multi_platform.py
import pytest

import backend.infrastructure.scrapers.multi_platform as mp


@pytest.mark.asyncio
async def test_scrape_route_persists_snapshots(monkeypatch):
    captured = {}

    async def fake_route(origin, destination, depart_date):
        return [
            {"flight_number": "HU7833", "airline": "海南航空", "dep_city": origin, "arr_city": destination,
             "dep_time": "09:30", "arr_time": "14:20", "duration": "4h50m", "transfer_count": 0,
             "price": 389, "date": depart_date, "platform": "携程"},
        ]

    async def fake_upsert(flights):
        captured["flights"] = flights

    async def fake_record(**kw):
        captured["status"] = kw["status"]

    monkeypatch.setattr(mp, "scrape_route_all_platforms", fake_route)
    monkeypatch.setattr(mp, "upsert_flights", fake_upsert)
    monkeypatch.setattr(mp, "record_job", fake_record)

    await mp.crawl_route("北京", "上海", "2026-05-01")
    assert captured["flights"][0]["flight_no"] == "HU7833"
    assert captured["status"] == "success"
```

- [ ] **Step 3: 运行测试确认失败**

Run: `pytest backend/tests/scrapers/test_multi_platform.py::test_scrape_route_persists_snapshots -v`
Expected: FAIL（`crawl_route` 不存在）

- [ ] **Step 4: 在 multi_platform.py 增加 crawl_route 并让 scrape_all_routes 调它**

在 `multi_platform.py` 顶部 import：

```python
from backend.data_sources.normalizer import normalize_raw_rows
from backend.infrastructure.db.flight_snapshot_repo import upsert_flights
from backend.infrastructure.db.crawl_job_repo import record_job
from backend.utils.airport_codes import city_to_code
```

新增函数并替换 `scrape_all_routes` 主体（高频航线池见 PRD §9.3）：

```python
HIGH_FREQ_ROUTES = [
    ("北京", "成都"), ("北京", "三亚"), ("北京", "上海"), ("北京", "广州"), ("北京", "杭州"),
]


async def crawl_route(origin: str, destination: str, depart_date: str) -> None:
    rows = await scrape_route_all_platforms(origin, destination, depart_date)
    flights = normalize_raw_rows(rows)
    platform_status = {r.get("platform", "?"): "ok" for r in rows}
    if not flights:
        await record_job(
            origin_code=city_to_code(origin), destination_code=city_to_code(destination),
            depart_date=depart_date, status="failed", platform_status=platform_status,
            error_message="no flights normalized",
        )
        return
    await upsert_flights(flights)
    await record_job(
        origin_code=city_to_code(origin), destination_code=city_to_code(destination),
        depart_date=depart_date, status="success", platform_status=platform_status,
    )


async def scrape_all_routes() -> None:
    from datetime import date, timedelta

    base = date.today() + timedelta(days=1)
    for origin, destination in HIGH_FREQ_ROUTES:
        try:
            await crawl_route(origin, destination, base.isoformat())
        except Exception:  # 单航线失败不影响其它航线
            continue
```

> 若现有 `scrape_route_all_platforms` 签名不接受 `depart_date`，先按现有 `scrape_route_all_platforms(query)` 调用约定调整本函数的传参；保持「单平台失败只影响该平台」语义不变。

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest backend/tests/scrapers/test_multi_platform.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/infrastructure/scrapers/multi_platform.py backend/infrastructure/db/crawl_job_repo.py backend/tests/scrapers/test_multi_platform.py
git commit -m "feat(crawler): persist normalized snapshots + crawl_jobs each hour"
```

---

## Task 6: 全量回归

- [ ] **Step 1:** Run: `pytest backend/tests/infra backend/tests/scrapers backend/tests/graph/tools -q` → Expected: PASS
- [ ] **Step 2:** 如需，提交测试修订。

---

## Self-Review

- **Spec coverage：** §5.2.5 三表 ✔ Task 1；§9.3 归一化/聚合/最低价 ✔ Task 2；读模型命中规则 ✔ Task 3；查询链路只读不触爬 ✔ Task 4；每小时落库 + crawl_jobs 状态 ✔ Task 5；data_freshness=stale 标记 ✔ Task 3。
- **Placeholder scan：** 无；Step 4 对 `scrape_route_all_platforms` 签名差异给了明确分支处理而非 TODO。
- **Type consistency：** `normalize_raw_rows` 输出 dict 键 ↔ `upsert_flights` 读取键 ↔ `read_deals` 输出键全程一致（flight_no/lowest_price/prices[]）。

## Execution Handoff

见末尾统一说明。
