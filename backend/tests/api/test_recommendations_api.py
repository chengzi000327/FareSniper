"""TG-12 Task 4: GET /api/recommendations cold-start and personalized."""
from __future__ import annotations

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient

from backend.infrastructure.db.flight_snapshot_repo import upsert_flights


@pytest.fixture(autouse=True)
def use_in_process_recommendation_cache(monkeypatch, fake_redis):
    monkeypatch.setattr(
        "backend.application.services.recommendation_service._redis",
        lambda: fake_redis,
    )


@pytest.mark.asyncio
async def test_cold_start_returns_hot_cards(
    seeded_pg, fake_redis, client: AsyncClient, valid_jwt_for_anon_new
):
    r = await client.get(
        "/api/recommendations",
        headers={"authorization": f"Bearer {valid_jwt_for_anon_new}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["personalized"] is False
    assert body["cards"] == []
    assert body["has_more"] is False


@pytest.mark.asyncio
async def test_personalized_when_memories_present(
    seeded_pg_with_memory, fake_redis, client: AsyncClient, valid_jwt_for_u1
):
    # personalized 由 user_preferences.frequent_cities 驱动(get_preferences 读的是
    # 新的 user_preferences 表,见 Task #10);只写老 memories 表不足以触发,
    # 这里补一条常去城市,且必须落在热门路线目的地内才会个性化排序靠前。
    from backend.infrastructure.db.base import get_session
    from backend.memory.long_term import LongTermMemory

    async with get_session() as db:
        await LongTermMemory(db).upsert_preferences("u1", {"frequent_cities": ["上海"]})
        await db.commit()
    depart_date = (
        datetime.now(ZoneInfo("Asia/Shanghai")).date() + timedelta(days=1)
    ).isoformat()
    await upsert_flights(
        [
            {
                "flight_no": "MU5106",
                "airline": "东方航空",
                "origin_code": "BJS",
                "destination_code": "SHA",
                "depart_date": depart_date,
                "dep_time": "08:00",
                "arr_time": "10:00",
                "duration": "2h",
                "stops": 0,
                "lowest_price": 580,
                "currency": "CNY",
                "prices": [
                    {
                        "platform": "携程",
                        "price": 580,
                        "currency": "CNY",
                    }
                ],
            }
        ]
    )

    r = await client.get(
        "/api/recommendations",
        headers={"authorization": f"Bearer {valid_jwt_for_u1}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["personalized"] is True


@pytest.mark.asyncio
async def test_rejects_without_token(client: AsyncClient):
    r = await client.get("/api/recommendations")
    assert r.status_code == 401
