from __future__ import annotations

from langchain_core.tools import tool

from backend.application.contracts.preference import Memory
from backend.application.services.preference_matcher import match


@tool
async def match_preferences(deals: list[dict], pref: dict) -> dict:
    """按用户偏好（预算上限/偏好航司/约束）过滤与排序候选航班。"""
    memory = Memory(
        budget_ceiling=pref.get("budget_ceiling"),
        preferred_airlines=pref.get("preferred_airlines", []),
        constraints=pref.get("constraints", []),
    )
    out = match(deals, memory)
    return {"filtered": out["filtered"], "boosted": out["boosted"]}
