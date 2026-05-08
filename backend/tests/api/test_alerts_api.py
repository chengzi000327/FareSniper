"""TG-12 Task 5: POST/GET /api/alerts with JWT auth."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_and_list_alerts(
    seeded_pg, client: AsyncClient, valid_jwt_for_u1
):
    headers = {"authorization": f"Bearer {valid_jwt_for_u1}"}
    r = await client.post(
        "/api/alerts",
        headers=headers,
        json={
            "origin": "BJS",
            "destination": "SYX",
            "depart_date": "2026-05-01",
            "target_price": 500,
        },
    )
    assert r.status_code == 201
    aid = r.json()["id"]
    rl = await client.get("/api/alerts", headers=headers)
    assert rl.status_code == 200
    assert any(a["id"] == aid for a in rl.json()["alerts"])


@pytest.mark.asyncio
async def test_alerts_rejects_without_token(client: AsyncClient):
    r = await client.get("/api/alerts")
    assert r.status_code == 401
