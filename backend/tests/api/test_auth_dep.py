"""TG-12 Task 8: Protected endpoint JWT regression guard."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_memory_requires_jwt(seeded_pg, client: AsyncClient):
    r = await client.get("/api/memory")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_memory_ignores_query_user_id(
    seeded_pg, client: AsyncClient, valid_jwt_for_u1
):
    r = await client.get(
        "/api/memory",
        params={"user_id": "u2"},
        headers={"authorization": f"Bearer {valid_jwt_for_u1}"},
    )
    assert r.status_code == 200
    # Backend uses token sub=u1, not query param u2
    assert all(m["field"] != "u2_only" for m in r.json()["memories"])


@pytest.mark.asyncio
async def test_alerts_require_jwt(client: AsyncClient):
    r = await client.get("/api/alerts")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_recommendations_require_jwt(client: AsyncClient):
    r = await client.get("/api/recommendations")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_track_jump_requires_jwt(client: AsyncClient):
    """track/jump guard — prevent regression to unauthenticated version."""
    r = await client.post(
        "/api/track/jump",
        json={
            "flight_no": "MU5137",
            "platform": "ctrip",
            "price": 480,
            "deeplink_ok": True,
        },
    )
    assert r.status_code == 401
