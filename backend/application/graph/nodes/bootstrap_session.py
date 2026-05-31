"""Bootstrap session context node."""

from __future__ import annotations

import logging

from backend.application.context.assembler import assemble_context
from backend.application.graph.state import WorkflowState

logger = logging.getLogger("faresniper.graph.bootstrap_session")


async def bootstrap_session_context(state: WorkflowState) -> WorkflowState:
    ctx = await assemble_context(
        session_id=state["request_session_id"],
        user_id=state["request_user_id"],
        message=state["request_message"],
        session_factory=state.get("_session_factory"),
        redis_client=state.get("_redis_client"),
    )
    clarify_count = await _get_clarify_count(
        state["request_session_id"], state.get("_redis_client")
    )
    return {**state, "context": ctx, "clarify_count": clarify_count}


async def _get_clarify_count(session_id: str | None, redis_client) -> int:
    if not session_id or not redis_client:
        return 0
    try:
        val = await redis_client.get(f"clarify:{session_id}")
        return int(val) if val else 0
    except Exception:
        return 0


# ── ReAct graph entry node (TG-08) ───────────────────────────────────────────
import uuid  # noqa: E402

from langchain_core.messages import SystemMessage  # noqa: E402

from backend.application.contracts.intent import SlotBundle  # noqa: E402
from backend.application.services.intent_examples import (  # noqa: E402
    fast_intent_match,
    render_intent_definitions,
)
from backend.application.services.intent_registry import load_intent_registry  # noqa: E402
from backend.infrastructure.redis.session_store import load_slots, save_slots  # noqa: E402


async def bootstrap_session(state: dict) -> dict:
    """Initialize or restore session: allocate session_id and load accumulated slots."""
    sid = state.get("request_session_id") or f"s_{uuid.uuid4().hex[:12]}"
    try:
        slots = await load_slots(sid) or SlotBundle()
        await save_slots(sid, slots)
    except Exception:
        logger.exception(
            "session_store_unavailable request_id=%s session_id=%s",
            state.get("request_id", ""),
            sid,
        )
        slots = SlotBundle()
    intent_definitions = []
    intent_definitions_text = ""
    fast_intent_hint_text = ""
    messages = []
    try:
        intent_definitions = await load_intent_registry()
        intent_definitions_text = render_intent_definitions(intent_definitions)
    except Exception:
        logger.warning("intent_registry_bootstrap_failed", exc_info=True)

    request_message = state.get("request_message") or _latest_user_text(state)
    if request_message:
        try:
            match = await fast_intent_match(request_message)
        except Exception:
            logger.warning("fast_intent_match_failed", exc_info=True)
            match = None
        if match:
            fast_intent_hint_text = (
                "[系统提示] 用户意图已预判为 "
                f"{match['intent_name']}（置信度 {match['confidence']:.2f}），"
                "请直接提取槽位或执行工具。"
            )
            messages.append(SystemMessage(content=fast_intent_hint_text))
    return {
        "request_session_id": sid,
        "accumulated_slots": slots,
        "clarify_count": state.get("clarify_count", 0),
        "fallback_triggered": state.get("fallback_triggered", False),
        "errors": state.get("errors", []),
        "intent_definitions": intent_definitions,
        "intent_definitions_text": intent_definitions_text,
        "fast_intent_hint_text": fast_intent_hint_text,
        "messages": messages,
    }


def _latest_user_text(state: dict) -> str:
    for message in reversed(list(state.get("messages") or [])):
        content = getattr(message, "content", None)
        if isinstance(content, str) and content.strip():
            return content
        if isinstance(message, dict):
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                return content
    return ""
