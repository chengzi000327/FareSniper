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
