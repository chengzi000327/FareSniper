"""TG-14 Task 3: verify intent_parsed and fallback_triggered are auto-emitted."""
from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage


@pytest.mark.asyncio
async def test_intent_parsed_emitted(monkeypatch, seeded_pg):
    """Running the graph with a stubbed LLM emits INTENT_PARSED to PG."""
    import backend.application.graph.nodes.bootstrap_session as bs
    import backend.application.graph.nodes.react_agent as ra
    import backend.application.graph.nodes.slot_filling as sf
    from backend.application.services.default_intents import DEFAULT_INTENTS
    from backend.infrastructure.db.event_repo import count_events
    from backend.analytics.events import EventName

    async def _fake_load(sid):
        return None

    async def _fake_save(sid, slots):
        return None

    monkeypatch.setattr(bs, "load_slots", _fake_load)
    monkeypatch.setattr(bs, "save_slots", _fake_save)
    monkeypatch.setattr(sf, "load_intent_registry", lambda: _async_value(DEFAULT_INTENTS))

    class _NoToolChat:
        model = "stub"

        def bind_tools(self, _tools):
            return self

        async def ainvoke(self, _messages):
            return AIMessage(content="没有找到相关航班")

    monkeypatch.setattr(ra, "build_chat_model", lambda role: _NoToolChat())

    from backend.application.graph.factory import build_graph

    g = build_graph()
    await g.ainvoke(
        {
            "messages": [HumanMessage(content="明天 BJS 到 SHA")],
            "request_user_id": "u1",
            "clarify_count": 0,
            "fallback_triggered": False,
            "errors": [],
        }
    )
    assert await count_events(EventName.INTENT_PARSED, user_id="u1") >= 1


async def _async_value(value):
    return value


@pytest.mark.asyncio
async def test_fallback_triggered_emitted_directly(seeded_pg):
    """fallback_form tool emits FALLBACK_TRIGGERED when called directly."""
    from backend.application.graph.tools.fallback_form import fallback_form
    from backend.infrastructure.db.event_repo import count_events
    from backend.analytics.events import EventName

    await fallback_form.arun({"reason": "clarify_count >= 2", "user_id": "u2"})
    assert await count_events(EventName.FALLBACK_TRIGGERED, user_id="u2") >= 1
