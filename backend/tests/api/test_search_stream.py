"""NDJSON streaming contract for progressive flight searches."""
from __future__ import annotations

import asyncio
import json
import logging

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
async def test_stream_complete_is_owned_by_flight_search_trace(
    search_client: AsyncClient, valid_jwt_for_u1, monkeypatch
):
    import backend.api.search as search_mod

    graph = _EventGraph()
    trace_calls: list[tuple[str, int]] = []
    complete_emit_calls = 0
    original_emit = search_mod.SearchEventEmitter.emit

    async def fake_trace_flight_search(request_id, message_length, operation):
        trace_calls.append((request_id, message_length))
        response = await operation()
        emit_search_event(
            "complete", {"response": response.model_dump(mode="json")}
        )
        return response

    def counting_emit(self, event_type, payload):
        nonlocal complete_emit_calls
        if event_type == "complete":
            complete_emit_calls += 1
        return original_emit(self, event_type, payload)

    monkeypatch.setattr(search_mod, "get_graph", lambda: graph)
    monkeypatch.setattr(
        search_mod, "trace_flight_search", fake_trace_flight_search, raising=False
    )
    monkeypatch.setattr(search_mod.SearchEventEmitter, "emit", counting_emit)

    response = await search_client.post(
        "/api/search/stream",
        headers={"authorization": f"Bearer {valid_jwt_for_u1}"},
        json={"session_id": None, "message": "北京到上海"},
    )
    events = [json.loads(line) for line in response.text.splitlines()]

    assert len(trace_calls) == 1
    assert trace_calls[0][1] == len("北京到上海")
    assert complete_emit_calls == 1
    assert [event["type"] for event in events].count("complete") == 1


@pytest.mark.asyncio
async def test_stream_graph_error_emits_one_sanitized_complete_event(
    search_client: AsyncClient, valid_jwt_for_u1, monkeypatch, caplog
):
    import backend.api.search as search_mod

    secret = "stream-secret-token?query=private&api_key=also-secret"

    class _FailingGraph:
        async def ainvoke(self, state, config=None):
            raise RuntimeError(secret)

    monkeypatch.setattr(search_mod, "get_graph", lambda: _FailingGraph())
    caplog.set_level(logging.ERROR, logger="faresniper.search")

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
    assert secret not in response.text
    assert secret not in caplog.text


@pytest.mark.asyncio
async def test_stream_uses_api_complete_after_graph_emits_complete(
    search_client: AsyncClient, valid_jwt_for_u1, monkeypatch
):
    import backend.api.search as search_mod

    class _GraphWithTerminalEvent:
        async def ainvoke(self, state, config=None):
            emit_search_event("started", {"providers": ["flyai"]})
            emit_search_event("complete", {"source": "graph"})
            emit_search_event("results", {"deals": [{"price": 580}]})
            return {
                **state,
                "request_session_id": "s_terminal",
                "response": FrontendResponse(
                    user_id=state["request_user_id"],
                    deals=[{"price": 580}],
                    analysis={},
                    recommendation={},
                    meta={},
                ),
            }

    monkeypatch.setattr(search_mod, "get_graph", lambda: _GraphWithTerminalEvent())

    response = await search_client.post(
        "/api/search/stream",
        headers={"authorization": f"Bearer {valid_jwt_for_u1}"},
        json={"session_id": None, "message": "北京到上海"},
    )
    events = [json.loads(line) for line in response.text.splitlines()]

    assert [event["type"] for event in events] == ["started", "results", "complete"]
    assert [event["sequence"] for event in events] == [1, 2, 3]
    assert len([event for event in events if event["type"] == "complete"]) == 1
    assert events[-1]["payload"] == {
        "response": {
            "user_id": "u1",
            "session_id": "s_terminal",
            "query": None,
            "deals": [{"price": 580}],
            "analysis": {},
            "recommendation": {},
            "meta": {},
        }
    }


@pytest.mark.asyncio
async def test_stream_emits_sanitized_failure_after_graph_emits_complete(
    search_client: AsyncClient, valid_jwt_for_u1, monkeypatch, caplog
):
    import backend.api.search as search_mod

    secret = "graph-terminal-secret?query=private&api_key=also-secret"

    class _GraphWithTerminalFailure:
        async def ainvoke(self, state, config=None):
            emit_search_event("started", {"providers": ["flyai"]})
            emit_search_event("complete", {"source": "graph"})
            raise RuntimeError(secret)

    monkeypatch.setattr(search_mod, "get_graph", lambda: _GraphWithTerminalFailure())
    caplog.set_level(logging.ERROR, logger="faresniper.search")

    response = await search_client.post(
        "/api/search/stream",
        headers={"authorization": f"Bearer {valid_jwt_for_u1}"},
        json={"session_id": None, "message": "北京到上海"},
    )
    events = [json.loads(line) for line in response.text.splitlines()]

    assert [event["type"] for event in events] == ["started", "complete"]
    assert [event["sequence"] for event in events] == [1, 2]
    assert events[-1]["payload"] == {
        "error": "search_failed",
        "message": "搜索暂时不可用，请稍后重试",
    }
    assert secret not in response.text
    assert secret not in caplog.text


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


@pytest.mark.asyncio
async def test_stream_asgi_disconnect_cancels_and_awaits_graph_task(
    valid_jwt_for_u1, monkeypatch
):
    import backend.api.search as search_mod

    cancelled = asyncio.Event()
    finished = asyncio.Event()

    class _BlockingGraph:
        async def ainvoke(self, state, config=None):
            emit_search_event("started", {"providers": ["flyai"]})
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise
            finally:
                finished.set()

    monkeypatch.setattr(search_mod, "get_graph", lambda: _BlockingGraph())
    app = FastAPI()
    app.include_router(search_router, prefix="/api")
    first_chunk_sent = asyncio.Event()
    request_received = False
    sent: list[dict] = []

    async def receive() -> dict:
        nonlocal request_received
        if not request_received:
            request_received = True
            return {
                "type": "http.request",
                "body": json.dumps(
                    {"session_id": None, "message": "北京到上海"}
                ).encode(),
                "more_body": False,
            }
        await first_chunk_sent.wait()
        return {"type": "http.disconnect"}

    async def send(message: dict) -> None:
        sent.append(message)
        if message["type"] == "http.response.body" and message.get("body"):
            first_chunk_sent.set()

    await app(
        {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/api/search/stream",
            "raw_path": b"/api/search/stream",
            "query_string": b"",
            "headers": [
                (b"authorization", f"Bearer {valid_jwt_for_u1}".encode()),
                (b"content-type", b"application/json"),
            ],
            "client": ("127.0.0.1", 123),
            "server": ("testserver", 80),
        },
        receive,
        send,
    )

    assert first_chunk_sent.is_set()
    assert cancelled.is_set()
    assert finished.is_set()
    assert any(message["type"] == "http.response.start" for message in sent)
