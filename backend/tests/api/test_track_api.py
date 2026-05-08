import asyncio
import pytest
from httpx import AsyncClient, ASGITransport
from backend.main import app
from backend.analytics.events import EventName
from backend.infrastructure.db.event_repo import count_events


@pytest.mark.asyncio
async def test_track_persists_with_jwt_user(seeded_pg, valid_jwt_for_u1):
    """user_id 必须从 JWT 解析；payload 里即使带 user_id 也被忽略。"""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/api/track",
            headers={"authorization": f"Bearer {valid_jwt_for_u1}"},
            json={
                "event": "search_submitted",
                "payload": {"user_id": "attacker_id", "query_text": "hi", "clarify_count": 0},
            },
        )
    assert r.status_code == 204
    assert await count_events(EventName.SEARCH_SUBMITTED, user_id="u1") == 1
    assert await count_events(EventName.SEARCH_SUBMITTED, user_id="attacker_id") == 0


@pytest.mark.asyncio
async def test_track_rejects_without_token(seeded_pg):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/api/track", json={"event": "search_submitted", "payload": {}})
    assert r.status_code == 401
