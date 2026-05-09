"""Runtime graph wires the PRD slot-filling flow."""

from __future__ import annotations

import pytest
from langchain_core.messages import HumanMessage


def test_build_graph_has_slot_filling_nodes():
    """build_graph() compiled graph contains all slot-filling node names."""
    from backend.application.graph.factory import build_graph

    g = build_graph()
    node_names = set(g.get_graph().nodes.keys())
    assert "bootstrap_session" in node_names
    assert "fill_intent_slots" in node_names
    assert "clarify_response" in node_names
    assert "run_slot_search" in node_names
    assert "render_response" in node_names


@pytest.mark.asyncio
async def test_build_graph_clarifies_missing_origin(monkeypatch):
    """Graph asks for one missing slot before search."""
    import backend.application.graph.nodes.bootstrap_session as bs
    import backend.application.graph.nodes.slot_filling as sf
    from backend.application.services.default_intents import DEFAULT_INTENTS

    async def _fake_load(sid):
        return None

    async def _fake_save(sid, slots):
        return None

    monkeypatch.setattr(bs, "load_slots", _fake_load)
    monkeypatch.setattr(bs, "save_slots", _fake_save)
    monkeypatch.setattr(sf, "load_intent_registry", lambda: _async_value(DEFAULT_INTENTS))

    from backend.application.graph.factory import build_graph

    g = build_graph()
    result = await g.ainvoke(
        {
            "messages": [HumanMessage(content="明天去三亚")],
            "request_message": "明天去三亚",
            "request_user_id": "u1",
        }
    )
    assert "response" in result
    assert result["response"] is not None
    assert result["response"].deals == []
    assert result["response"].meta["missing_slots"] == ["origin"]
    assert "从哪里出发" in result["response"].recommendation["text"]


@pytest.mark.asyncio
async def test_build_graph_searches_when_slots_complete(monkeypatch):
    """Graph calls search only after required slots are complete."""
    import backend.application.graph.nodes.bootstrap_session as bs
    import backend.application.graph.nodes.slot_filling as sf
    from backend.application.services.default_intents import DEFAULT_INTENTS

    async def _fake_load(sid):
        return None

    async def _fake_save(sid, slots):
        return None

    async def _fake_search(args):
        return {
            "deals": [{"flight_no": "MU5137", "price": 480}],
            "source": "cache",
        }

    class _FakeSearchTool:
        async def ainvoke(self, args):
            return await _fake_search(args)

    monkeypatch.setattr(bs, "load_slots", _fake_load)
    monkeypatch.setattr(bs, "save_slots", _fake_save)
    monkeypatch.setattr(sf, "load_intent_registry", lambda: _async_value(DEFAULT_INTENTS))
    monkeypatch.setattr(sf, "search_flights", _FakeSearchTool())

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
    import backend.application.graph.nodes.bootstrap_session as bs
    import backend.application.graph.nodes.slot_filling as sf
    from backend.application.services.default_intents import DEFAULT_INTENTS

    async def _fake_load(sid):
        return None

    async def _fake_save(sid, slots):
        return None

    monkeypatch.setattr(bs, "load_slots", _fake_load)
    monkeypatch.setattr(bs, "save_slots", _fake_save)
    monkeypatch.setattr(sf, "load_intent_registry", lambda: _async_value(DEFAULT_INTENTS))

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
async def test_build_graph_handles_smalltalk(monkeypatch):
    import backend.application.graph.nodes.bootstrap_session as bs
    import backend.application.graph.nodes.slot_filling as sf
    from backend.application.services.default_intents import DEFAULT_INTENTS

    async def _fake_load(sid):
        return None

    async def _fake_save(sid, slots):
        return None

    monkeypatch.setattr(bs, "load_slots", _fake_load)
    monkeypatch.setattr(bs, "save_slots", _fake_save)
    monkeypatch.setattr(sf, "load_intent_registry", lambda: _async_value(DEFAULT_INTENTS))

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
    assert result["response"].meta["intent"] == "smalltalk"
    assert result["response"].recommendation["action"] == "smalltalk"
    assert "FareSniper" in result["response"].recommendation["text"]


async def _async_value(value):
    return value
