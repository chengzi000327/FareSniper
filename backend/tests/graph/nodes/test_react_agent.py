from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from backend.application.graph.nodes.react_agent import react_agent


@pytest.mark.asyncio
async def test_react_emits_tool_call_when_slots_complete(
    stub_chat_model_for_search, monkeypatch
):
    import backend.application.graph.nodes.react_agent as ra

    monkeypatch.setattr(ra, "build_chat_model", lambda role: stub_chat_model_for_search)

    state = {
        "messages": [HumanMessage(content="明天从北京去上海")],
        "accumulated_slots": None,
        "clarify_count": 0,
        "request_user_id": "u1",
    }
    out = await react_agent(state)
    last = out["messages"][-1]
    assert isinstance(last, AIMessage)
    assert any(tc["name"] == "search_flights" for tc in (last.tool_calls or []))


@pytest.mark.asyncio
async def test_react_routes_missing_date_to_deterministic_clarification(monkeypatch):
    import backend.application.graph.nodes.react_agent as ra

    model_built = False

    def _build_model(*args, **kwargs):
        nonlocal model_built
        model_built = True
        raise AssertionError("the model must not guess a missing date")

    monkeypatch.setattr(ra, "build_chat_model", _build_model)

    out = await ra.react_agent(
        {
            "messages": [HumanMessage(content="北京到上海的机票")],
            "request_message": "北京到上海的机票",
            "accumulated_slots": None,
            "intent_definitions": [],
            "request_user_id": "u1",
        }
    )

    assert out == {"llm_failed": True}
    assert model_built is False


@pytest.mark.asyncio
async def test_react_agent_marks_llm_failed_on_exception(monkeypatch):
    import backend.application.graph.nodes.react_agent as ra

    class _Boom:
        def bind_tools(self, tools):
            return self

        async def ainvoke(self, messages):
            raise RuntimeError("llm down")

    monkeypatch.setattr(ra, "load_available_tools", lambda: [])
    monkeypatch.setattr(ra, "build_chat_model", lambda role="agent": _Boom())
    monkeypatch.setattr(ra, "load_prompt", lambda name: "SYS")

    out = await ra.react_agent({"messages": [HumanMessage(content="嗨")], "request_user_id": "u1"})
    assert out.get("llm_failed") is True
    assert "messages" not in out


@pytest.mark.asyncio
async def test_react_agent_renders_intent_definitions_into_system(monkeypatch):
    import backend.application.graph.nodes.react_agent as ra

    seen = {}

    class _Chat:
        def bind_tools(self, tools):
            return self

        async def ainvoke(self, messages):
            seen["system"] = messages[0]["content"]
            return AIMessage(content="ok")

    monkeypatch.setattr(ra, "load_available_tools", lambda: [])
    monkeypatch.setattr(ra, "build_chat_model", lambda role="agent": _Chat())
    monkeypatch.setattr(ra, "load_prompt", lambda name: "SYS\n{intent_definitions}")

    out = await ra.react_agent(
        {
            "messages": [HumanMessage(content="嗨")],
            "request_user_id": "u1",
            "intent_definitions_text": "- search_flight: 查机票",
        }
    )

    assert out["messages"][0].content == "ok"
    assert "- search_flight: 查机票" in seen["system"]
