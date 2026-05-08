"""Bootstrap session context node."""

from __future__ import annotations

from backend.application.context.assembler import assemble_context
from backend.application.graph.state import WorkflowState


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

from backend.application.contracts.intent import SlotBundle  # noqa: E402
from backend.infrastructure.redis.session_store import load_slots, save_slots  # noqa: E402


async def bootstrap_session(state: dict) -> dict:
    """Initialize or restore session: allocate session_id and load accumulated slots."""
    sid = state.get("request_session_id") or f"s_{uuid.uuid4().hex[:12]}"
    slots = await load_slots(sid) or SlotBundle()
    await save_slots(sid, slots)
    return {
        "request_session_id": sid,
        "accumulated_slots": slots,
        "clarify_count": state.get("clarify_count", 0),
        "fallback_triggered": state.get("fallback_triggered", False),
        "errors": state.get("errors", []),
    }
