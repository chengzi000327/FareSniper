from __future__ import annotations

import asyncio
import logging

from backend.application.graph._now import today_cn
from backend.application.graph.tools import load_available_tools
from backend.application.services.intent_slot_filler import (
    fill_slots,
    missing_required_slots,
)
from backend.infrastructure.llm.models import build_chat_model
from backend.infrastructure.llm.prompt_loader import load_prompt

logger = logging.getLogger("faresniper.graph.react_agent")

LLM_TIMEOUT_SECONDS = 8.0


async def react_agent(state: dict) -> dict:
    """ReAct LLM node: bind tools and invoke the chat model; on failure flag llm_failed for rule fallback."""
    if _search_requires_clarification(state):
        return {"llm_failed": True}

    tools = load_available_tools()
    chat = build_chat_model(role="agent")
    if tools:
        chat = chat.bind_tools(tools)

    system = load_prompt("react_agent")
    system = system.replace(
        "{intent_definitions}",
        state.get("intent_definitions_text") or "暂无动态意图定义",
    )
    # 注入当前日期(北京时区),让 LLM 能把"明天/后天/下周末/五一"等相对说法
    # 推算成具体 YYYY-MM-DD;否则模型不知道今天几号,出发日会算错。
    system = (
        f"今天是 {today_cn()}。涉及日期的工具参数(如 depart_date)必须基于今天"
        f"推算成具体的 YYYY-MM-DD 格式。\n\n{system}"
    )
    if state.get("fast_intent_hint_text"):
        system = f"{system}\n{state['fast_intent_hint_text']}"
    messages = [{"role": "system", "content": system}, *list(state["messages"])]

    try:
        ai = await asyncio.wait_for(chat.ainvoke(messages), timeout=LLM_TIMEOUT_SECONDS)
    except Exception:
        logger.warning(
            "react_agent_llm_failed user_id=%s", state.get("request_user_id", ""), exc_info=True
        )
        return {"llm_failed": True}

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


def _search_requires_clarification(state: dict) -> bool:
    text = str(state.get("request_message") or _latest_user_text(state))
    if not text.strip():
        return False
    definitions = state.get("intent_definitions") or None
    slots = fill_slots(
        text,
        state.get("accumulated_slots"),
        intent_definitions=definitions,
    )
    return slots.intent == "search_flight" and bool(
        missing_required_slots(slots, definitions)
    )


def _latest_user_text(state: dict) -> str:
    for message in reversed(list(state.get("messages") or [])):
        if getattr(message, "type", "") == "human":
            return str(getattr(message, "content", ""))
        if isinstance(message, dict) and message.get("role") == "user":
            return str(message.get("content") or "")
    return ""
