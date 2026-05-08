"""TG-12 Task 3: GET/PATCH/DELETE /api/memory with JWT auth."""
from __future__ import annotations

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_get_returns_memories_and_history(
    seeded_pg_with_memory, client: AsyncClient, valid_jwt_for_u1
):
    r = await client.get(
        "/api/memory", headers={"authorization": f"Bearer {valid_jwt_for_u1}"}
    )
    assert r.status_code == 200
    body = r.json()
    assert "memories" in body and "query_history" in body


@pytest.mark.asyncio
async def test_patch_upserts(seeded_pg, client: AsyncClient, valid_jwt_for_u1):
    r = await client.patch(
        "/api/memory",
        headers={"authorization": f"Bearer {valid_jwt_for_u1}"},
        json={"field": "budget_ceiling", "value": 600},
    )
    assert r.status_code == 200


@pytest.mark.asyncio
async def test_delete_field(
    seeded_pg_with_memory, client: AsyncClient, valid_jwt_for_u1
):
    r = await client.delete(
        "/api/memory/budget_ceiling",
        headers={"authorization": f"Bearer {valid_jwt_for_u1}"},
    )
    assert r.status_code == 204


@pytest.mark.asyncio
async def test_get_rejects_without_token(client: AsyncClient):
    r = await client.get("/api/memory")
    assert r.status_code == 401
