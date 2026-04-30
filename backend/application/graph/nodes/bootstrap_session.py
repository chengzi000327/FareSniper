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
