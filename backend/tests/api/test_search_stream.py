"""NDJSON streaming contract for progressive flight searches."""
from __future__ import annotations

import asyncio
import json

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from starlette.requests import Request

from backend.api.search import router as search_router
from backend.application.contracts.decision import FrontendResponse
from backend.application.services.search_events import emit_search_event


@pytest_asyncio.fixture
async def search_client():
    app = FastAPI()
    app.include_router(search_router, prefix="/api")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


class _EventGraph:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def ainvoke(self, state, config=None):
        self.calls.append({"state": state, "config": config})
        emit_search_event("started", {"providers": ["flyai", "ctrip"]})
        emit_search_event(
            "provider_status", {"provider": "flyai", "status": "loading"}
        )
        emit_search_event("results", {"deals": [{"price": 580}]})
        return {
            **state,
            "request_session_id": "s_stream",
            "response": FrontendResponse(
                user_id=state["request_user_id"],
                session_id="s_stream",
                deals=[{"price": 580}],
                analysis={},
                recommendation={"text": "找到结果"},
                meta={},
            ),
        }


@pytest.mark.asyncio
async def test_stream_requires_auth(search_client: AsyncClient):
    response = await search_client.post(
        "/api/search/stream",
        json={"session_id": None, "message": "北京到上海"},
    )

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_stream_emits_ordered_ndjson_with_complete_response(
    search_client: AsyncClient, valid_jwt_for_u1, monkeypatch
):
    import backend.api.search as search_mod

    graph = _EventGraph()
    monkeypatch.setattr(search_mod, "get_graph", lambda: graph)

    response = await search_client.post(
        "/api/search/stream",
        headers={"authorization": f"Bearer {valid_jwt_for_u1}"},
        json={"session_id": "s_existing", "message": "北京到上海"},
    )
    events = [json.loads(line) for line in response.text.splitlines()]

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/x-ndjson")
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-accel-buffering"] == "no"
    assert [event["sequence"] for event in events] == list(range(1, len(events) + 1))
    assert len({event["search_id"] for event in events}) == 1
    assert [event["type"] for event in events] == [
        "started",
        "provider_status",
        "results",
        "complete",
    ]
    assert events[-1]["payload"]["response"] == {
        "user_id": "u1",
        "session_id": "s_stream",
        "query": None,
        "deals": [{"price": 580}],
        "analysis": {},
        "recommendation": {"text": "找到结果"},
        "meta": {},
    }
    assert graph.calls[0]["state"]["request_session_id"] == "s_existing"
    assert graph.calls[0]["state"]["request_message"] == "北京到上海"
    assert graph.calls[0]["state"]["messages"][0].content == "北京到上海"
    assert graph.calls[0]["config"] == {"recursion_limit": 15}


@pytest.mark.asyncio
async def test_stream_graph_error_emits_one_sanitized_complete_event(
    search_client: AsyncClient, valid_jwt_for_u1, monkeypatch
):
    import backend.api.search as search_mod

    class _FailingGraph:
        async def ainvoke(self, state, config=None):
            raise RuntimeError(
                "token=super-secret api_key=also-secret ?query=private"
            )

    monkeypatch.setattr(search_mod, "get_graph", lambda: _FailingGraph())

    response = await search_client.post(
        "/api/search/stream",
        headers={"authorization": f"Bearer {valid_jwt_for_u1}"},
        json={"session_id": None, "message": "北京到上海"},
    )
    events = [json.loads(line) for line in response.text.splitlines()]

    assert response.status_code == 200
    assert [event["type"] for event in events] == ["complete"]
    assert events[0]["payload"] == {
        "error": "search_failed",
        "message": "搜索暂时不可用，请稍后重试",
    }
    assert "super-secret" not in response.text
    assert "also-secret" not in response.text
    assert "private" not in response.text


@pytest.mark.asyncio
async def test_stream_disconnect_cancels_and_awaits_graph_task(monkeypatch):
    import backend.api.search as search_mod

    stream_handler = getattr(search_mod, "search_stream", None)
    assert stream_handler is not None, "stream endpoint must exist"

    cancelled = asyncio.Event()

    class _BlockingGraph:
        async def ainvoke(self, state, config=None):
            emit_search_event("started", {"providers": ["flyai"]})
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise

    monkeypatch.setattr(search_mod, "get_graph", lambda: _BlockingGraph())
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/search/stream",
            "headers": [],
            "app": FastAPI(),
        }
    )
    response = await stream_handler(
        search_mod.SearchReq(session_id=None, message="北京到上海"), request, "u1"
    )

    await anext(response.body_iterator)
    await response.body_iterator.aclose()

    await asyncio.wait_for(cancelled.wait(), timeout=0.5)
