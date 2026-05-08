from __future__ import annotations

import pytest

from backend.infrastructure.db.query_history_repo import (
    append_query,
    list_query_history,
)


@pytest.mark.asyncio
async def test_append_then_list(seeded_pg):
    await append_query("u1", "明天去三亚")
    await append_query("u1", "国庆飞西安")
    rows = await list_query_history("u1", limit=10)
    assert len(rows) == 2
    assert rows[0].query_text == "国庆飞西安"  # desc by created_at


@pytest.mark.asyncio
async def test_limit_truncates(seeded_pg):
    for i in range(5):
        await append_query("u1", f"q{i}")
    rows = await list_query_history("u1", limit=3)
    assert len(rows) == 3
