import asyncio
from unittest.mock import AsyncMock

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


@pytest.mark.asyncio
@pytest.mark.parametrize("event", ["ticket_clicked", "purchase_jumped"])
async def test_click_events_learn_with_jwt_user_and_sanitized_payload(
    event, seeded_pg, valid_jwt_for_u1, monkeypatch
):
    learner = AsyncMock()
    monkeypatch.setattr("backend.api.track.learn_from_click", learner)
    payload = {
        "user_id": "attacker_id",
        "flight_no": "CZ6718",
        "platform": "飞猪",
        "price": 650,
        "signals": ["低价"],
        "airline": "南方航空",
        "origin": "北京",
        "destination": "三亚",
        "depart_date": "2026-07-24",
        "booking_url": "https://example.invalid/should-not-be-learned",
    }

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        response = await c.post(
            "/api/track",
            headers={"authorization": f"Bearer {valid_jwt_for_u1}"},
            json={"event": event, "payload": payload},
        )

    assert response.status_code == 204
    learner.assert_awaited_once()
    learned_uid, learned_payload, session_factory = learner.await_args.args
    assert learned_uid == "u1"
    assert learned_payload == {
        "flight_no": "CZ6718",
        "platform": "飞猪",
        "price": 650,
        "signals": ["低价"],
        "airline": "南方航空",
        "origin": "北京",
        "destination": "三亚",
        "depart_date": "2026-07-24",
    }
    assert "user_id" not in learned_payload
    assert session_factory is not None
