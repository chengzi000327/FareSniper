from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import ClickHistory, QueryHistory, UserPreference

FIELD_LABELS = {
    "budget": "心理价位",
    "frequent_cities": "常去城市",
    "preferred_airlines": "偏好航司",
    "constraints": "出行习惯",
    "travel_scenes": "出行场景",
}


class LongTermMemory:
    """PostgreSQL 持久化记忆：用户偏好 + 查询/点击历史。"""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    # ── Preferences ──────────────────────────────────────────────────────

    async def get_preferences(self, user_id: str) -> dict[str, Any] | None:
        result = await self._s.get(UserPreference, user_id)
        if result is None:
            return None
        return {
            "budget": result.budget,
            "frequent_cities": result.frequent_cities or [],
            "preferred_airlines": result.preferred_airlines or [],
            "constraints": result.constraints or [],
            "travel_scenes": result.travel_scenes or [],
        }

    async def upsert_preferences(self, user_id: str, data: dict[str, Any]) -> None:
        mapped = self._map_pref_fields(data)
        stmt = (
            insert(UserPreference)
            .values(id=user_id, **mapped)
            .on_conflict_do_update(index_elements=["id"], set_=mapped)
        )
        await self._s.execute(stmt)
        await self._s.flush()

    # ── Query History ────────────────────────────────────────────────────

    async def add_query(
        self, user_id: str, query_text: str, intent: dict[str, Any] | None = None
    ) -> None:
        record = QueryHistory(user_id=user_id, query_text=query_text, intent=intent or {})
        self._s.add(record)
        await self._s.flush()

    async def get_recent_queries(self, user_id: str, limit: int = 10) -> list[dict[str, Any]]:
        stmt = (
            select(QueryHistory)
            .where(QueryHistory.user_id == user_id)
            .order_by(QueryHistory.created_at.desc())
            .limit(limit)
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [
            {"query_text": r.query_text, "intent": r.intent, "created_at": str(r.created_at)}
            for r in rows
        ]

    # ── Click History ─────────────────────────────────────────────────────

    async def add_click(self, user_id: str, flight_data: dict[str, Any]) -> None:
        record = ClickHistory(user_id=user_id, flight_data=flight_data)
        self._s.add(record)
        await self._s.flush()

    async def get_recent_clicks(self, user_id: str, limit: int = 10) -> list[dict[str, Any]]:
        stmt = (
            select(ClickHistory)
            .where(ClickHistory.user_id == user_id)
            .order_by(ClickHistory.clicked_at.desc())
            .limit(limit)
        )
        rows = (await self._s.execute(stmt)).scalars().all()
        return [
            {"flight_data": r.flight_data, "clicked_at": str(r.clicked_at)}
            for r in rows
        ]

    # ── Internal ──────────────────────────────────────────────────────────

    @staticmethod
    def _map_pref_fields(data: dict[str, Any]) -> dict[str, Any]:
        allowed = {"budget", "frequent_cities", "preferred_airlines", "constraints", "travel_scenes"}
        return {k: v for k, v in data.items() if k in allowed}
