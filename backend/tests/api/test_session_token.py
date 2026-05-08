"""TG-12 Task 9: /api/session anonymous JWT regression."""
from __future__ import annotations

import jwt
import pytest
from httpx import AsyncClient

from backend.config import settings


@pytest.mark.asyncio
async def test_session_returns_anon_jwt(seeded_pg, client: AsyncClient):
    r = await client.post("/api/session", json={})
    assert r.status_code == 200
    body = r.json()
    assert "access_token" in body
    payload = jwt.decode(
        body["access_token"], settings.jwt_secret, algorithms=["HS256"]
    )
    assert payload["sub"] == body["user_id"]
    assert payload.get("anon") is True
