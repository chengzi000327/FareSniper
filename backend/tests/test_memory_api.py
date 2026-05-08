"""Memory API regression tests (JWT auth)."""
from __future__ import annotations


async def test_get_memory_returns_200(seeded_pg, client, valid_jwt_for_u1):
    resp = await client.get(
        "/api/memory", headers={"authorization": f"Bearer {valid_jwt_for_u1}"}
    )
    assert resp.status_code == 200


async def test_get_memory_schema(seeded_pg, client, valid_jwt_for_u1):
    resp = await client.get(
        "/api/memory", headers={"authorization": f"Bearer {valid_jwt_for_u1}"}
    )
    body = resp.json()
    assert "memories" in body
    assert "query_history" in body


async def test_patch_memory(seeded_pg, client, valid_jwt_for_u1):
    resp = await client.patch(
        "/api/memory",
        headers={"authorization": f"Bearer {valid_jwt_for_u1}"},
        json={"field": "price_anchor", "value": 3000},
    )
    assert resp.status_code == 200


async def test_delete_memory_field(seeded_pg, client, valid_jwt_for_u1):
    resp = await client.delete(
        "/api/memory/price_anchor",
        headers={"authorization": f"Bearer {valid_jwt_for_u1}"},
    )
    assert resp.status_code == 204
