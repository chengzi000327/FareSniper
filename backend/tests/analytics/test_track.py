from __future__ import annotations

import pytest

from backend.analytics.events import EventName
from backend.analytics.track import track
from backend.infrastructure.db.event_repo import count_events


@pytest.mark.asyncio
async def test_track_persists_event(seeded_pg):
    await track(
        EventName.SEARCH_SUBMITTED,
        user_id="u1",
        payload={"query_text": "BJS->SYX", "user_id": "u1", "clarify_count": 0},
    )
    n = await count_events(EventName.SEARCH_SUBMITTED, user_id="u1")
    assert n == 1


@pytest.mark.asyncio
async def test_track_rejects_missing_required(seeded_pg):
    with pytest.raises(ValueError, match="missing required field: query_text"):
        await track(
            EventName.SEARCH_SUBMITTED,
            user_id="u1",
            payload={"user_id": "u1", "clarify_count": 0},
        )


@pytest.mark.asyncio
async def test_count_events_isolated_by_user(seeded_pg):
    await track(
        EventName.SEARCH_SUBMITTED,
        user_id="u1",
        payload={"query_text": "x", "user_id": "u1", "clarify_count": 0},
    )
    await track(
        EventName.SEARCH_SUBMITTED,
        user_id="u2",
        payload={"query_text": "y", "user_id": "u2", "clarify_count": 0},
    )
    assert await count_events(EventName.SEARCH_SUBMITTED, user_id="u1") == 1
    assert await count_events(EventName.SEARCH_SUBMITTED, user_id="u2") == 1
