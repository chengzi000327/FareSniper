"""TG-08 Task 6: build_graph() wires the full ReAct loop."""

from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage


def test_build_graph_has_react_nodes():
    """build_graph() compiled graph contains all ReAct node names."""
    from backend.application.graph.factory import build_graph

    g = build_graph()
    node_names = set(g.get_graph().nodes.keys())
    assert "bootstrap_session" in node_names
    assert "react_agent" in node_names
    assert "tool_router" in node_names
    assert "render_response" in node_names


@pytest.mark.asyncio
async def test_build_graph_end_to_end_no_tool_calls(monkeypatch):
    """Graph runs to render_response when LLM emits no tool calls."""
    import backend.application.graph.nodes.bootstrap_session as bs
    import backend.application.graph.nodes.react_agent as ra
    from backend.application.graph.nodes.bootstrap_session import SlotBundle

    # Stub Redis calls in bootstrap_session
    async def _fake_load(sid):
        return None

    async def _fake_save(sid, slots):
        return None

    monkeypatch.setattr(bs, "load_slots", _fake_load)
    monkeypatch.setattr(bs, "save_slots", _fake_save)

    class _NoToolChat:
        model = "stub"

        def bind_tools(self, _tools):
            return self

        async def ainvoke(self, _messages):
            return AIMessage(content="没有找到相关航班")

    monkeypatch.setattr(ra, "build_chat_model", lambda role: _NoToolChat())

    from backend.application.graph.factory import build_graph

    g = build_graph()
    result = await g.ainvoke(
        {
            "messages": [HumanMessage(content="查一下北京到上海的航班")],
            "request_user_id": "u1",
        }
    )
    assert "response" in result
    assert result["response"] is not None
