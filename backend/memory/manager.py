from __future__ import annotations

from typing import Any

from backend.memory.long_term import LongTermMemory
from backend.memory.short_term import ShortTermMemory
from backend.memory.summarizer import MemorySummarizer


class MemoryManager:
    """聚合短期记忆 + 长期记忆 + 摘要，提供统一的上下文接口。"""

    def __init__(
        self,
        short_term: ShortTermMemory,
        long_term: LongTermMemory,
        summarizer: MemorySummarizer,
    ) -> None:
        self._stm = short_term
        self._ltm = long_term
        self._summarizer = summarizer

    async def get_full_context(self, user_id: str, session_id: str) -> dict[str, Any]:
        """
        返回：
        {
            "short_term": [...],          # 最近 N 条对话
            "preferences": {...},         # 用户偏好，无数据时为 {}
            "long_term_summary": "...",   # 自然语言摘要
        }
        """
        short_term, preferences, recent_queries = await self._fetch_all(user_id)

        summary = await self._summarizer.summarize(user_id, preferences, recent_queries)

        return {
            "short_term": short_term,
            "preferences": preferences or {},
            "long_term_summary": summary,
        }

    async def push_message(self, user_id: str, message: dict[str, Any]) -> None:
        await self._stm.push(user_id, message)

    async def save_query(self, user_id: str, query_text: str, intent: dict[str, Any]) -> None:
        await self._ltm.add_query(user_id, query_text, intent)

    async def save_click(self, user_id: str, flight_data: dict[str, Any]) -> None:
        await self._ltm.add_click(user_id, flight_data)

    async def update_preferences(self, user_id: str, data: dict[str, Any]) -> None:
        await self._ltm.upsert_preferences(user_id, data)

    # ── Internal ──────────────────────────────────────────────────────────

    async def _fetch_all(
        self, user_id: str
    ) -> tuple[list[dict], dict[str, Any] | None, list[dict]]:
        import asyncio
        short_term, preferences, recent_queries = await asyncio.gather(
            self._stm.get(user_id),
            self._ltm.get_preferences(user_id),
            self._ltm.get_recent_queries(user_id, limit=5),
        )
        return short_term, preferences, recent_queries
