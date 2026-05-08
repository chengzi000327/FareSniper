"""TG-12 Task 2: POST /api/search invokes graph and enforces JWT."""
from __future__ import annotations

import pytest
from httpx import AsyncClient

from backend.application.contracts.decision import FrontendResponse


def _make_fake_graph(session_id: str = "s_test123"):
    """Return an object whose ainvoke returns a minimal FrontendResponse state."""

    class _FakeGraph:
        async def ainvoke(self, state, config=None):
            rsp = FrontendResponse(
                user_id=state.get("request_user_id", ""),
                deals=[],
                analysis={},
                recommendation={},
                meta={},
            )
            return {**state, "response": rsp, "request_session_id": session_id}

    return _FakeGraph()


@pytest.mark.asyncio
async def test_search_rejects_without_token(client: AsyncClient):
    r = await client.post("/api/search", json={"session_id": None, "message": "x"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_search_returns_response_dto(
    seeded_pg, client: AsyncClient, valid_jwt_for_u1, monkeypatch
):
    import backend.api.search as search_mod

    monkeypatch.setattr(search_mod, "get_graph", lambda: _make_fake_graph())

    r = await client.post(
        "/api/search",
        headers={"authorization": f"Bearer {valid_jwt_for_u1}"},
        json={"session_id": None, "message": "明天 BJS 到 SHA"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "deals" in body
    assert body["session_id"] is not None
