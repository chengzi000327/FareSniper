"""推荐瀑布流兜底:未来 3 天无数据时回退到该路线最新日期;
history_avg_90d 缺失时用同航线近期市场均价计算折扣。"""
from __future__ import annotations

import pytest

from backend.application.services.recommendation_service import (
    _build_recommendations_uncached,
)
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


@pytest.mark.asyncio
async def test_falls_back_to_latest_date_when_no_future_data(seeded_pg):
    # 只 seed 一个很旧的日期(绝不在未来 3 天内),且多航班
    await upsert_flights([_flight("SHA", 280, "MU1"), _flight("SHA", 600, "MU2")])

    rsp = await _build_recommendations_uncached("anon-fallback")

    sha = next(c for c in rsp.cards if c.title.endswith("上海"))
    # 兜底到旧日期 → preview_deal 应有真实数据,而非 None
    assert sha.preview_deal is not None
    assert sha.preview_deal["price"] == 280
    assert sha.preview_deal["depart_date"] == "2020-01-01"


@pytest.mark.asyncio
async def test_discount_uses_market_avg_when_history_missing(seeded_pg):
    await upsert_flights([_flight("SHA", 280, "MU1"), _flight("SHA", 600, "MU2")])

    rsp = await _build_recommendations_uncached("anon-fallback")

    sha = next(c for c in rsp.cards if c.title.endswith("上海"))
    # market_avg=(280+600)/2=440 → discount=round((440-280)/440*100)=36
    assert sha.discount_pct == 36
