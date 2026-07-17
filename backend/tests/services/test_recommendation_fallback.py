"""Recommendation feed future-date and discount fallback behavior."""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

import backend.application.services.recommendation_service as svc
from backend.infrastructure.db.flight_snapshot_repo import upsert_flights


def _flight(
    dest: str,
    price: int,
    fno: str,
    depart_date: str | None = None,
) -> dict:
    effective_date = depart_date or (
        datetime.now(ZoneInfo("Asia/Shanghai")).date() + timedelta(days=1)
    ).isoformat()
    return {
        "flight_no": fno,
        "airline": "东方航空",
        "origin_code": "BJS",
        "destination_code": dest,
        "depart_date": effective_date,
        "currency": "CNY",
        "dep_time": "08:00",
        "arr_time": "10:00",
        "duration": "2h",
        "stops": 0,
        "lowest_price": price,
        "history_avg_90d": None,
        "history_low_90d": None,
        "prices": [{"platform": "携程", "price": price, "currency": "CNY", "lowest": True, "url": ""}],
    }


@pytest.fixture
def patched_redis(fake_redis, monkeypatch):
    monkeypatch.setattr(svc, "_redis", lambda: fake_redis)
    return fake_redis


@pytest.mark.asyncio
async def test_historical_inventory_is_not_used_when_no_future_data(seeded_pg, patched_redis):
    await upsert_flights([
        _flight("SHA", 280, "MU1", "2020-01-01"),
        _flight("SHA", 600, "MU2", "2020-01-01"),
    ])

    rsp = await svc.build_recommendations("anon-fallback", limit=15, offset=0)

    assert rsp.cards == []


@pytest.mark.asyncio
async def test_discount_uses_market_median_when_history_missing(seeded_pg, patched_redis):
    # 样本≥3 才用当批中位数:280/600/650 → median=600 → (600-280)/600=53→封顶 50
    await upsert_flights([
        _flight("SHA", 280, "MU1"),
        _flight("SHA", 600, "MU2"),
        _flight("SHA", 650, "MU3"),
    ])

    rsp = await svc.build_recommendations("anon-fallback", limit=15, offset=0)

    sha = next(c for c in rsp.cards if c.title.endswith("上海"))
    assert sha.discount_pct == 50
