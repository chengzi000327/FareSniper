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
