from __future__ import annotations

from langchain_core.tools import tool

from backend.infrastructure.db.base import get_session


@tool
async def get_preferences(user_id: str) -> dict:
    """读取用户长期偏好。返回 dict 形式，便于 LLM 直接消费。"""
    async with get_session() as db:
        from backend.memory.long_term import LongTermMemory

        ltm = LongTermMemory(db)
        prefs = await ltm.get_preferences(user_id)
        return prefs or {}
