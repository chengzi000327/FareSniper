from __future__ import annotations

from backend.application.graph.tools import load_available_tools
from backend.infrastructure.llm.models import build_chat_model
from backend.infrastructure.llm.prompt_loader import load_prompt


async def react_agent(state: dict) -> dict:
    """ReAct LLM node: bind tools and invoke the chat model."""
    tools = load_available_tools()
    chat = build_chat_model(role="agent")
    if tools:
        chat = chat.bind_tools(tools)

    system = load_prompt("react_agent")
    messages = [{"role": "system", "content": system}, *list(state["messages"])]
    ai = await chat.ainvoke(messages)

    try:
        from backend.analytics.events import EventName
        from backend.analytics.track import track

        await track(
            EventName.INTENT_PARSED,
            user_id=state.get("request_user_id", ""),
            payload={"intent_complete": bool(ai.tool_calls), "parse_failed": False},
        )
    except Exception:
        pass

    return {"messages": [ai]}
