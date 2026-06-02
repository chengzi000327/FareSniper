"""推荐瀑布流兜底:未来 3 天无数据时回退到该路线最新日期;
history_avg_90d 缺失时用同航线近期市场中位数计算折扣(样本≥3 才计)。"""
from __future__ import annotations

import pytest

import backend.application.services.recommendation_service as svc
from backend.infrastructure.db.flight_snapshot_repo import upsert_flights


def _flight(dest: str, price: int, fno: str, depart_date: str = "2020-01-01") -> dict:
    return {
        "flight_no": fno,
        "airline": "东方航空",
        "origin_code": "BJS",
        "destination_code": dest,
        "depart_date": depart_date,
        "dep_time": "08:00",
        "arr_time": "10:00",
        "duration": "2h",
        "stops": 0,
        "lowest_price": price,
        "history_avg_90d": None,
        "history_low_90d": None,
        "prices": [{"platform": "携程", "price": price, "lowest": True, "url": ""}],
    }


@pytest.fixture
def patched_redis(fake_redis, monkeypatch):
    monkeypatch.setattr(svc, "_redis", lambda: fake_redis)
    return fake_redis


@pytest.mark.asyncio
async def test_falls_back_to_latest_date_when_no_future_data(seeded_pg, patched_redis):
    # 只 seed 一个很旧的日期(绝不在未来 3 天内),且多航班
    await upsert_flights([_flight("SHA", 280, "MU1"), _flight("SHA", 600, "MU2")])

    rsp = await svc.build_recommendations("anon-fallback", limit=15, offset=0)

    sha = next(c for c in rsp.cards if c.title.endswith("上海"))
    # 兜底到旧日期 → preview_deal 应有真实数据,而非 None
    assert sha.preview_deal is not None
    assert sha.preview_deal["price"] == 280
    assert sha.preview_deal["depart_date"] == "2020-01-01"


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
