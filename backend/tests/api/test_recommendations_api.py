"""TG-12 Task 4: GET /api/recommendations cold-start and personalized."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


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
    assert len(body["cards"]) >= 3


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
