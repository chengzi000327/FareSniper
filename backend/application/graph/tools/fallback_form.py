from __future__ import annotations

from langchain_core.tools import tool


@tool
async def fallback_form(reason: str, user_id: str | None = None) -> dict:
    """当 clarify_count >= 2 时调用，让前端弹出结构化表单 Modal。
    user_id 可选 — 由 force_fallback 节点透传，用于自动埋点 fallback_triggered 事件。
    """
    if user_id:
        try:
            from backend.analytics.events import EventName
            from backend.analytics.track import track

            await track(EventName.FALLBACK_TRIGGERED, user_id=user_id, payload={"reason": reason})
        except Exception:
            pass
    return {
        "ui": "modal",
        "fields": ["origin", "destination", "depart_date", "budget"],
        "reason": reason,
    }
