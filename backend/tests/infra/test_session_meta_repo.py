from __future__ import annotations

import pytest

from backend.infrastructure.db.session_meta_repo import (
    create_session_meta,
    get_session_meta,
    touch_session,
)


@pytest.mark.asyncio
async def test_create_and_get(seeded_pg):
    await create_session_meta("sess-001", "u1", slots={"origin": "BJS"})
    row = await get_session_meta("sess-001")
    assert row is not None
    assert row.user_id == "u1"
    assert row.slots["origin"] == "BJS"


@pytest.mark.asyncio
async def test_touch_updates_turn_count(seeded_pg):
    await create_session_meta("sess-002", "u1")
    await touch_session("sess-002", slots={"destination": "SYX"})
    row = await get_session_meta("sess-002")
    assert row.turn_count == 1
    assert row.slots["destination"] == "SYX"


@pytest.mark.asyncio
async def test_get_missing_returns_none(seeded_pg):
    row = await get_session_meta("nonexistent-session")
    assert row is None
