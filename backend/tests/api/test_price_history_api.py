"""TG-12 Task 7: GET /api/price_history."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_returns_points_when_available(
    seeded_pg_with_history, client: AsyncClient
):
    r = await client.get(
        "/api/price_history",
        params={"origin": "BJS", "destination": "SYX", "days": 30},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["route"] == "BJS-SYX"
    assert len(body["points"]) >= 1


@pytest.mark.asyncio
async def test_returns_empty_when_no_data(seeded_pg, client: AsyncClient):
    r = await client.get(
        "/api/price_history",
        params={"origin": "BJS", "destination": "CTU", "days": 30},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["route"] == "BJS-CTU"
    assert body["points"] == []
