"""TG-12 Task 1: POST /api/session anonymous JWT issuance."""
from __future__ import annotations

import jwt
import pytest
from httpx import AsyncClient

from backend.config import settings


@pytest.mark.asyncio
async def test_create_session_returns_ids(seeded_pg, client: AsyncClient):
    r = await client.post("/api/session", json={})
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"].startswith("anon_")
    assert body["session_id"].startswith("s_")
    assert body["access_token"]


@pytest.mark.asyncio
async def test_create_session_with_existing_user_id(seeded_pg, client: AsyncClient):
    r = await client.post("/api/session", json={"user_id": "anon_existing"})
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == "anon_existing"
    assert body["session_id"].startswith("s_")
    assert body["access_token"]
    payload = jwt.decode(
        body["access_token"], settings.jwt_secret, algorithms=["HS256"]
    )
    assert payload["sub"] == "anon_existing"
    assert payload.get("anon") is True
