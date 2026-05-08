from __future__ import annotations

from langchain_core.tools import tool

from backend.infrastructure.db.memory_repo import list_memories


@tool
async def get_preferences(user_id: str) -> dict:
    """读取用户长期偏好。返回 dict 形式，便于 LLM 直接消费。"""
    rows = await list_memories(user_id)
    return {m.field: m.value for m in rows}
