from __future__ import annotations

import pytest

from backend.infrastructure.db.memory_repo import (
    delete_field,
    list_memories,
    upsert_memory,
)


@pytest.mark.asyncio
async def test_upsert_then_list(seeded_pg):
    await upsert_memory("u1", "preferred_airlines", ["CA", "MU"], source="learned")
    rows = await list_memories("u1")
    assert any(m.field == "preferred_airlines" for m in rows)


@pytest.mark.asyncio
async def test_delete_field(seeded_pg):
    await upsert_memory("u1", "budget_ceiling", 500, source="user")
    await delete_field("u1", "budget_ceiling")
    rows = await list_memories("u1")
    assert all(m.field != "budget_ceiling" for m in rows)
