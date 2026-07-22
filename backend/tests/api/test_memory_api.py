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
async def test_get_combines_learned_preferences_manual_memory_and_query_history(
    seeded_pg, client: AsyncClient, valid_jwt_for_u1
):
    from backend.infrastructure.db.base import get_session
    from backend.infrastructure.db.memory_repo import upsert_memory
    from backend.infrastructure.db.query_history_repo import append_query
    from backend.memory.long_term import LongTermMemory

    async with get_session() as db:
        await LongTermMemory(db).upsert_preferences(
            "u1",
            {
                "budget": 680,
                "frequent_cities": ["三亚", "成都"],
                "preferred_airlines": ["南方航空"],
                "constraints": ["direct_only"],
                "travel_scenes": ["亲子游"],
            },
        )
        await db.commit()
    await upsert_memory("u1", "seat_preference", "靠窗", source="user")
    await append_query(
        "u1",
        "下周五北京飞三亚",
        intent={
            "destination": {"city": "三亚", "iata_code": "SYX"},
            "date_window": {"start_date": "2026-07-24"},
        },
    )

    response = await client.get(
        "/api/memory", headers={"authorization": f"Bearer {valid_jwt_for_u1}"}
    )

    assert response.status_code == 200
    body = response.json()
    by_field = {item["field"]: item for item in body["memories"]}
    assert set(by_field) == {
        "budget",
        "frequent_cities",
        "preferred_airlines",
        "constraints",
        "travel_scenes",
        "seat_preference",
    }
    assert by_field["budget"] == {
        "field": "budget",
        "value": 680,
        "label": "心理价位",
        "value_display": "¥680",
        "source": "auto",
    }
    assert by_field["frequent_cities"]["value_display"] == "三亚、成都"
    assert by_field["constraints"]["value_display"] == "只看直飞"
    assert by_field["seat_preference"] == {
        "field": "seat_preference",
        "value": "靠窗",
        "label": "座位偏好",
        "value_display": "靠窗",
        "source": "manual",
    }

    assert len(body["query_history"]) == 1
    history = body["query_history"][0]
    assert isinstance(history["id"], int)
    assert history["query"] == {
        "text": "下周五北京飞三亚",
        "intent": {
            "destination": {"city": "三亚", "iata_code": "SYX"},
            "date_window": {"start_date": "2026-07-24"},
        },
    }
    assert history["created_at"]


@pytest.mark.asyncio
async def test_get_omits_unlearned_empty_preference_fields(
    seeded_pg, client: AsyncClient, valid_jwt_for_u1
):
    from backend.infrastructure.db.base import get_session
    from backend.memory.long_term import LongTermMemory

    async with get_session() as db:
        await LongTermMemory(db).upsert_preferences(
            "u1", {"budget": 680, "frequent_cities": []}
        )
        await db.commit()

    response = await client.get(
        "/api/memory", headers={"authorization": f"Bearer {valid_jwt_for_u1}"}
    )

    by_field = {item["field"]: item for item in response.json()["memories"]}
    assert set(by_field) == {"budget"}


@pytest.mark.asyncio
async def test_patch_preference_updates_agent_memory_and_keeps_manual_override(
    seeded_pg, client: AsyncClient, valid_jwt_for_u1
):
    from backend.infrastructure.db.base import get_session
    from backend.infrastructure.db.memory_repo import list_memories
    from backend.memory.long_term import LongTermMemory

    r = await client.patch(
        "/api/memory",
        headers={"authorization": f"Bearer {valid_jwt_for_u1}"},
        json={"field": "budget", "value": 600},
    )
    assert r.status_code == 200

    rows = await list_memories("u1")
    budget_override = next(row for row in rows if row.field == "budget")
    assert budget_override.value == 600
    assert budget_override.source == "user"

    async with get_session() as db:
        memory = LongTermMemory(db)
        assert (await memory.get_preferences("u1"))["budget"] == 600
        await memory.upsert_preferences("u1", {"budget": 900})
        await db.commit()

    async with get_session() as db:
        # A later automatic update must not silently replace the correction.
        assert (await LongTermMemory(db).get_preferences("u1"))["budget"] == 600

    body = (
        await client.get(
            "/api/memory",
            headers={"authorization": f"Bearer {valid_jwt_for_u1}"},
        )
    ).json()
    budget = next(item for item in body["memories"] if item["field"] == "budget")
    assert budget["value"] == 600
    assert budget["source"] == "manual"


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
async def test_delete_preference_forgets_agent_value_and_manual_override(
    seeded_pg, client: AsyncClient, valid_jwt_for_u1
):
    from backend.infrastructure.db.base import get_session
    from backend.infrastructure.db.memory_repo import list_memories
    from backend.memory.long_term import LongTermMemory

    await client.patch(
        "/api/memory",
        headers={"authorization": f"Bearer {valid_jwt_for_u1}"},
        json={"field": "preferred_airlines", "value": ["中国国航"]},
    )
    response = await client.delete(
        "/api/memory/preferred_airlines",
        headers={"authorization": f"Bearer {valid_jwt_for_u1}"},
    )

    assert response.status_code == 204
    assert all(row.field != "preferred_airlines" for row in await list_memories("u1"))
    async with get_session() as db:
        preferences = await LongTermMemory(db).get_preferences("u1")
    assert preferences is not None
    assert preferences["preferred_airlines"] == []


@pytest.mark.asyncio
async def test_get_rejects_without_token(client: AsyncClient):
    r = await client.get("/api/memory")
    assert r.status_code == 401
