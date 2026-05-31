"""Runtime graph wires the ReAct-primary + rule-fallback flow."""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage


def test_build_graph_wires_react_primary_with_rule_fallback():
    from backend.application.graph.factory import build_graph

    g = build_graph()
    node_names = set(g.get_graph().nodes.keys())
    assert {"bootstrap_session", "react_agent", "tool_router", "render_response"} <= node_names
    assert {"fill_intent_slots", "clarify_response", "run_slot_search", "dynamic_intent_response"} <= node_names


@pytest.mark.asyncio
async def test_llm_failure_falls_back_to_rule_clarify(monkeypatch):
    import backend.application.graph.nodes.bootstrap_session as bs
    import backend.application.graph.nodes.slot_filling as sf
    import backend.application.graph.nodes.react_agent as ra
    from backend.application.services.default_intents import DEFAULT_INTENTS

    monkeypatch.setattr(bs, "load_slots", lambda sid: _async_value(None))
    monkeypatch.setattr(bs, "save_slots", lambda sid, slots: _async_value(None))
    monkeypatch.setattr(sf, "load_intent_registry", lambda: _async_value(DEFAULT_INTENTS))

    async def _failing_agent(state):
        return {"llm_failed": True}
    monkeypatch.setattr(ra, "react_agent", _failing_agent)

    from backend.application.graph.factory import build_graph
    g = build_graph()
    result = await g.ainvoke(
        {
            "messages": [HumanMessage(content="明天去三亚")],
            "request_message": "明天去三亚",
            "request_user_id": "u1",
        }
    )
    assert result["response"].deals == []
    assert result["response"].meta["missing_slots"] == ["origin"]
    assert "从哪里出发" in result["response"].recommendation["text"]



@pytest.mark.asyncio
async def test_build_graph_searches_when_slots_complete(monkeypatch):
    """Graph calls search only after required slots are complete (via rule fallback path)."""
    import backend.application.graph.nodes.bootstrap_session as bs
    import backend.application.graph.nodes.react_agent as ra
    import backend.application.graph.nodes.slot_filling as sf
    from backend.application.services.default_intents import DEFAULT_INTENTS

    async def _fake_search(args):
        return {
            "deals": [{"flight_no": "MU5137", "price": 480}],
            "source": "cache",
        }

    class _FakeSearchTool:
        async def ainvoke(self, args):
            return await _fake_search(args)

    monkeypatch.setattr(bs, "load_slots", lambda sid: _async_value(None))
    monkeypatch.setattr(bs, "save_slots", lambda sid, slots: _async_value(None))
    monkeypatch.setattr(sf, "load_intent_registry", lambda: _async_value(DEFAULT_INTENTS))
    monkeypatch.setattr(sf, "search_flights", _FakeSearchTool())

    async def _failing_agent(state):
        return {"llm_failed": True}

    monkeypatch.setattr(ra, "react_agent", _failing_agent)

    from backend.application.graph.factory import build_graph

    g = build_graph()
    result = await g.ainvoke(
        {
            "messages": [HumanMessage(content="明天北京到三亚")],
            "request_message": "明天北京到三亚",
            "request_user_id": "u1",
        }
    )

    assert result["response"].deals == [{"flight_no": "MU5137", "price": 480}]
    assert result["response"].query["origin_city"] == "北京"
    assert result["response"].query["destination_city"] == "三亚"
    assert result["response"].meta["source"] == "cache"


@pytest.mark.asyncio
async def test_build_graph_routes_dynamic_non_search_intent(monkeypatch):
    """Dynamic non-search intent is handled via rule fallback path."""
    import backend.application.graph.nodes.bootstrap_session as bs
    import backend.application.graph.nodes.react_agent as ra
    import backend.application.graph.nodes.slot_filling as sf
    from backend.application.services.default_intents import DEFAULT_INTENTS

    monkeypatch.setattr(bs, "load_slots", lambda sid: _async_value(None))
    monkeypatch.setattr(bs, "save_slots", lambda sid, slots: _async_value(None))
    monkeypatch.setattr(sf, "load_intent_registry", lambda: _async_value(DEFAULT_INTENTS))

    async def _failing_agent(state):
        return {"llm_failed": True}

    monkeypatch.setattr(ra, "react_agent", _failing_agent)

    from backend.application.graph.factory import build_graph

    g = build_graph()
    result = await g.ainvoke(
        {
            "messages": [HumanMessage(content="明天北京到三亚低于500提醒我")],
            "request_message": "明天北京到三亚低于500提醒我",
            "request_user_id": "u1",
        }
    )

    assert result["response"].deals == []
    assert result["response"].meta["intent"] == "set_alert"
    assert result["response"].meta["handler_name"] == "set_alert"


@pytest.mark.asyncio
async def test_build_graph_handles_chitchat(monkeypatch):
    """Chitchat intent is handled via rule fallback path."""
    import backend.application.graph.nodes.bootstrap_session as bs
    import backend.application.graph.nodes.react_agent as ra
    import backend.application.graph.nodes.slot_filling as sf
    from backend.application.services.default_intents import DEFAULT_INTENTS

    monkeypatch.setattr(bs, "load_slots", lambda sid: _async_value(None))
    monkeypatch.setattr(bs, "save_slots", lambda sid, slots: _async_value(None))
    monkeypatch.setattr(sf, "load_intent_registry", lambda: _async_value(DEFAULT_INTENTS))

    async def _failing_agent(state):
        return {"llm_failed": True}

    monkeypatch.setattr(ra, "react_agent", _failing_agent)

    from backend.application.graph.factory import build_graph

    g = build_graph()
    result = await g.ainvoke(
        {
            "messages": [HumanMessage(content="你是谁？")],
            "request_message": "你是谁？",
            "request_user_id": "u1",
        }
    )

    assert result["response"].deals == []
    assert result["response"].meta["intent"] == "chitchat"
    assert result["response"].recommendation["action"] == "chitchat"
    assert "FareSniper" in result["response"].recommendation["text"]


async def _async_value(value):
    return value
