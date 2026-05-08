from __future__ import annotations

from langchain_core.tools import tool

from backend.infrastructure.db.alert_repo import create_alert


@tool
async def set_alert(
    origin: str,
    destination: str,
    depart_date: str,
    target_price: int,
    injected_user_id: str | None = None,
) -> dict:
    """当用户明确表达"监控这条航线价格"意图时调用。
    `injected_user_id` 必填，由 graph 的 tool_router 节点从 state 注入；
    LLM schema 中命名为 injected_user_id，tool_router 显式覆盖，防止 LLM 伪造他人账号。
    """
    if not injected_user_id:
        raise ValueError("_user_id required (must be injected by tool_router)")
    aid = await create_alert(
        injected_user_id,
        origin=origin,
        destination=destination,
        depart_date=depart_date,
        target_price=target_price,
    )
    return {
        "alert_id": aid,
        "status": "active",
        "summary": f"已为你监控 {origin}→{destination} {depart_date}，≤ {target_price} 元时通知",
    }
