from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, ToolMessage


def _make_fake_tool(name: str, return_value):
    """Create a minimal tool-shaped object that tool_router can call."""

    class _FakeTool:
        def __init__(self):
            self.name = name

        async def ainvoke(self, args):
            return return_value

    return _FakeTool()


def _make_asserting_tool(name: str, expected_args: dict, return_value):
    class _FakeTool:
        def __init__(self):
            self.name = name

        async def ainvoke(self, args):
            assert args == expected_args
            return return_value

    return _FakeTool()


@pytest.mark.asyncio
async def test_executes_search_flights_tool_call(monkeypatch):
    """search_flights tool call must produce a ToolMessage."""
    import backend.application.graph.nodes.tool_router as tr

    fake = _make_fake_tool("search_flights", {"deals": [{"flight_no": "MU5137", "price": 480}]})
    monkeypatch.setattr(tr, "load_available_tools", lambda: [fake])

    ai = AIMessage(
        content="",
        tool_calls=[
            {
                "id": "c1",
                "name": "search_flights",
                "args": {"origin": "BJS", "destination": "SHA", "depart_date": "2026-05-08"},
            }
        ],
    )
    out = await tr.tool_router({"messages": [ai], "clarify_count": 0, "request_user_id": "u1"})
    tm = out["messages"][-1]
    assert isinstance(tm, ToolMessage)
    assert tm.tool_call_id == "c1"
    assert out["search_result"] is not None


@pytest.mark.asyncio
async def test_ask_user_increments_clarify_count(monkeypatch):
    import backend.application.graph.nodes.tool_router as tr

    fake = _make_fake_tool("ask_user", {"question": "请问您想去哪里？"})
    monkeypatch.setattr(tr, "load_available_tools", lambda: [fake])

    ai = AIMessage(
        content="",
        tool_calls=[
            {
                "id": "c2",
                "name": "ask_user",
                "args": {"missing_field": "destination", "context": "ctx"},
            }
        ],
    )
    out = await tr.tool_router({"messages": [ai], "clarify_count": 1, "request_user_id": "u1"})
    assert out["clarify_count"] == 2


@pytest.mark.asyncio
async def test_unknown_tool_returns_error_tool_message(monkeypatch):
    import backend.application.graph.nodes.tool_router as tr

    monkeypatch.setattr(tr, "load_available_tools", lambda: [])

    ai = AIMessage(
        content="",
        tool_calls=[{"id": "c3", "name": "not_yet_implemented", "args": {}}],
    )
    out = await tr.tool_router({"messages": [ai], "clarify_count": 0, "request_user_id": "u1"})
    assert "not implemented" in out["messages"][-1].content


@pytest.mark.asyncio
async def test_get_preferences_injects_user_id_with_tool_schema(monkeypatch):
    import backend.application.graph.nodes.tool_router as tr

    fake = _make_asserting_tool(
        "get_preferences",
        {"user_id": "u1"},
        {"budget_ceiling": 800},
    )
    monkeypatch.setattr(tr, "load_available_tools", lambda: [fake])

    ai = AIMessage(
        content="",
        tool_calls=[
            {
                "id": "c4",
                "name": "get_preferences",
                "args": {"user_id": "attacker"},
            }
        ],
    )
    out = await tr.tool_router({"messages": [ai], "clarify_count": 0, "request_user_id": "u1"})
    assert isinstance(out["messages"][-1], ToolMessage)
