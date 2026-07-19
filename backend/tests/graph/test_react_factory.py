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

    assert result["response"].deals[0]["flight_no"] == "MU5137"
    assert result["response"].deals[0]["price"] == 480
    assert result["response"].deals[0]["recommend_score"]
    assert result["response"].query["origin_city"] == "北京"
    assert result["response"].query["destination_city"] == "三亚"
    assert result["response"].meta["source"] == "cache"


@pytest.mark.asyncio
async def test_build_graph_restores_route_for_date_only_followup(
    fake_redis, monkeypatch
):
    import backend.application.graph.nodes.bootstrap_session as bs
    import backend.application.graph.nodes.react_agent as ra
    import backend.application.graph.nodes.slot_filling as sf
    import backend.infrastructure.redis.session_store as session_store
    from backend.application.services.default_intents import DEFAULT_INTENTS
    from backend.application.graph.factory import build_graph

    class _FakeSearchTool:
        async def ainvoke(self, args):
            assert args == {
                "origin": "北京",
                "destination": "三亚",
                "depart_date": "2026-07-25",
            }
            return {
                "deals": [{"flight_no": "MU5137", "price": 480}],
                "source": "cache",
            }

    def _unexpected_model(*args, **kwargs):
        raise AssertionError("slot continuation must bypass the chat model")

    monkeypatch.setattr(session_store, "_pool", fake_redis)
    monkeypatch.setattr(
        bs, "load_intent_registry", lambda: _async_value(DEFAULT_INTENTS)
    )
    monkeypatch.setattr(bs, "fast_intent_match", lambda text: _async_value(None))
    monkeypatch.setattr(
        sf, "load_intent_registry", lambda: _async_value(DEFAULT_INTENTS)
    )
    monkeypatch.setattr(sf, "search_flights", _FakeSearchTool())
    monkeypatch.setattr(ra, "build_chat_model", _unexpected_model)

    graph = build_graph()
    first = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="北京到三亚")],
            "request_message": "北京到三亚",
            "request_session_id": "s_followup",
            "request_user_id": "u1",
        }
    )
    assert first["response"].meta["missing_slots"] == ["depart_date"]

    second = await graph.ainvoke(
        {
            "messages": [HumanMessage(content="2026年7月25日")],
            "request_message": "2026年7月25日",
            "request_session_id": "s_followup",
            "request_user_id": "u1",
        }
    )

    assert second["response"].deals[0]["flight_no"] == "MU5137"
    assert second["response"].query["origin_city"] == "北京"
    assert second["response"].query["destination_city"] == "三亚"
    assert second["response"].query["date_start"] == "2026-07-25"


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
