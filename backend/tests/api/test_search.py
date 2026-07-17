"""POST /api/search invokes the graph and preserves its JSON contract."""
from __future__ import annotations

import logging

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from backend.api.search import router as search_router
from backend.application.contracts.decision import FrontendResponse


@pytest_asyncio.fixture
async def search_client():
    app = FastAPI()
    app.include_router(search_router, prefix="/api")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


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


def _make_capturing_fake_graph(calls: list[dict], session_id: str = "s_capture"):
    class _FakeGraph:
        async def ainvoke(self, state, config=None):
            calls.append({"state": state, "config": config})
            return {
                **state,
                "response": FrontendResponse(
                    user_id=state["request_user_id"],
                    deals=[{"price": 580}],
                    analysis={},
                    recommendation={"text": "找到结果"},
                    meta={},
                ),
                "request_session_id": session_id,
            }

    return _FakeGraph()


@pytest.mark.asyncio
async def test_search_rejects_without_token(search_client: AsyncClient):
    r = await search_client.post(
        "/api/search", json={"session_id": None, "message": "x"}
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_search_returns_response_dto(
    search_client: AsyncClient, valid_jwt_for_u1, monkeypatch
):
    import backend.api.search as search_mod

    monkeypatch.setattr(search_mod, "get_graph", lambda: _make_fake_graph())

    r = await search_client.post(
        "/api/search",
        headers={"authorization": f"Bearer {valid_jwt_for_u1}"},
        json={"session_id": None, "message": "明天 BJS 到 SHA"},
    )
    assert r.status_code == 200
    body = r.json()
    assert "deals" in body
    assert body["session_id"] is not None


@pytest.mark.asyncio
async def test_search_preserves_graph_input_and_response_contract(
    search_client: AsyncClient, valid_jwt_for_u1, monkeypatch
):
    import backend.api.search as search_mod

    calls: list[dict] = []
    monkeypatch.setattr(
        search_mod, "get_graph", lambda: _make_capturing_fake_graph(calls)
    )

    response = await search_client.post(
        "/api/search",
        headers={"authorization": f"Bearer {valid_jwt_for_u1}"},
        json={"session_id": "s_existing", "message": "北京到上海"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "user_id": "u1",
        "session_id": "s_capture",
        "query": None,
        "deals": [{"price": 580}],
        "analysis": {},
        "recommendation": {"text": "找到结果"},
        "meta": {},
    }
    assert len(calls) == 1
    state = calls[0]["state"]
    assert state["request_user_id"] == "u1"
    assert state["request_session_id"] == "s_existing"
    assert state["request_message"] == "北京到上海"
    assert state["messages"][0].content == "北京到上海"
    assert calls[0]["config"] == {"recursion_limit": 15}


@pytest.mark.asyncio
async def test_search_error_logs_safe_context_without_exception_text(
    search_client: AsyncClient, valid_jwt_for_u1, monkeypatch, caplog
):
    import backend.api.search as search_mod

    secret = "legacy-secret-token?query=private&api_key=also-secret"

    class _FailingGraph:
        async def ainvoke(self, state, config=None):
            raise RuntimeError(secret)

    monkeypatch.setattr(search_mod, "get_graph", lambda: _FailingGraph())
    caplog.set_level(logging.ERROR, logger="faresniper.search")

    with pytest.raises(RuntimeError) as error:
        await search_client.post(
            "/api/search",
            headers={"authorization": f"Bearer {valid_jwt_for_u1}"},
            json={"session_id": None, "message": "北京到上海"},
        )

    assert str(error.value) == secret
    assert secret not in caplog.text
    assert "search_graph_failed request_id=" in caplog.text
