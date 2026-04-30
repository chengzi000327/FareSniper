"""Clarification response node."""

from __future__ import annotations

from datetime import datetime, timezone

from backend.application.contracts.decision import FrontendResponse
from backend.application.graph.state import WorkflowState

_PROMPTS = {
    "origin": "请问您从哪个城市出发？",
    "destination": "请问目的地是哪里？",
    "date": "请问什么时间出发？",
}


async def clarify_response(state: WorkflowState) -> WorkflowState:
    intent = state.get("intent")
    count = (state.get("clarify_count") or 0) + 1

    if count >= 2:
        text = "填一下这几项吧"
    elif not intent or not (intent.origin and intent.origin.city):
        text = _PROMPTS["origin"]
    elif not (intent.destination and intent.destination.city):
        text = _PROMPTS["destination"]
    else:
        text = _PROMPTS["date"]

    await _save_clarify_count(state, count)

    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    resp = FrontendResponse(
        user_id=state["request_user_id"],
        query=None,
        deals=[],
        analysis={"match_score": 0, "within_budget": False, "matched_preferences": []},
        recommendation={"action": "watch", "text": text, "confidence": "low", "signals": []},
        meta={"generated_at": now, "fallback_mode": False, "clarify_count": count},
    )
    return {**state, "response": resp, "clarify_count": count}


async def _save_clarify_count(state: WorkflowState, count: int) -> None:
    redis = state.get("_redis_client")
    session_id = state.get("request_session_id")
    if not redis or not session_id:
        return
    try:
        await redis.setex(f"clarify:{session_id}", 1800, count)
    except Exception:
        pass
