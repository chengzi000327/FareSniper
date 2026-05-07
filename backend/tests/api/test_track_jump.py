from __future__ import annotations

import pytest
from httpx import AsyncClient

from backend.analytics.events import EventName
from backend.infrastructure.db.event_repo import count_events


@pytest.mark.asyncio
async def test_track_jump_returns_204(seeded_pg, client: AsyncClient, valid_jwt_for_u1):
    response = await client.post(
        "/api/track/jump",
        headers={"Authorization": f"Bearer {valid_jwt_for_u1}"},
        json={
            "flight_no": "MU5137",
            "platform": "ctrip",
            "price": 480,
            "deeplink_ok": True,
        },
    )
    assert response.status_code == 204


@pytest.mark.asyncio
async def test_track_jump_persists_event_with_user_from_jwt(
    seeded_pg, client: AsyncClient, valid_jwt_for_u1
):
    response = await client.post(
        "/api/track/jump",
        headers={"Authorization": f"Bearer {valid_jwt_for_u1}"},
        json={
            "flight_no": "MU5137",
            "platform": "ctrip",
            "price": 480,
            "deeplink_ok": True,
        },
    )
    assert response.status_code == 204
    assert await count_events(EventName.PURCHASE_JUMPED, user_id="u1") == 1
    assert await count_events(EventName.PURCHASE_JUMPED, user_id="u2") == 0


@pytest.mark.asyncio
async def test_track_jump_rejects_without_token(seeded_pg, client: AsyncClient):
    response = await client.post(
        "/api/track/jump",
        json={
            "flight_no": "MU5137",
            "platform": "ctrip",
            "price": 480,
            "deeplink_ok": True,
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_track_jump_rejects_garbage_token(seeded_pg, client: AsyncClient):
    response = await client.post(
        "/api/track/jump",
        headers={"Authorization": "Bearer not-a-jwt"},
        json={
            "flight_no": "MU5137",
            "platform": "ctrip",
            "price": 480,
            "deeplink_ok": True,
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_track_jump_rejects_missing_required_field(
    seeded_pg, client: AsyncClient, valid_jwt_for_u1
):
    response = await client.post(
        "/api/track/jump",
        headers={"Authorization": f"Bearer {valid_jwt_for_u1}"},
        json={"flight_no": "MU5137", "platform": "ctrip"},
    )
    assert response.status_code == 422
