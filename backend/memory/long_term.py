from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import ChatHistory, ClickHistory, QueryHistory, UserPreference

FIELD_LABELS = {
    "price_anchor": "心理价位",
    "preferred_origins": "常用出发地",
    "preferred_destinations": "想去的地方",
    "frequent_destinations": "常去目的地",
    "travel_window": "出行时间偏好",
    "cabin_preference": "舱位偏好",
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
            "price_anchor": result.price_anchor,
            "preferred_origins": result.preferred_origins or [],
            "preferred_destinations": result.preferred_destinations or [],
            "frequent_destinations": result.frequent_destinations or [],
            "travel_window": result.travel_window,
            "cabin_preference": result.cabin_preference,
            "extra": result.extra or {},
        }

    async def upsert_preferences(self, user_id: str, data: dict[str, Any]) -> None:
        stmt = (
            insert(UserPreference)
            .values(id=user_id, **self._map_pref_fields(data))
            .on_conflict_do_update(
                index_elements=["id"],
                set_=self._map_pref_fields(data),
            )
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
        result = await self._s.execute(stmt)
        rows = result.scalars().all()
        return [{"query_text": r.query_text, "intent": r.intent, "created_at": str(r.created_at)} for r in rows]

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
        result = await self._s.execute(stmt)
        rows = result.scalars().all()
        return [{"flight_data": r.flight_data, "clicked_at": str(r.clicked_at)} for r in rows]

    # ── Internal ──────────────────────────────────────────────────────────

    @staticmethod
    def _map_pref_fields(data: dict[str, Any]) -> dict[str, Any]:
        mapping = {
            "price_anchor": "price_anchor",
            "preferred_origins": "preferred_origins",
            "preferred_destinations": "preferred_destinations",
            "frequent_destinations": "frequent_destinations",
            "travel_window": "travel_window",
            "cabin_preference": "cabin_preference",
            "extra": "extra",
        }
        return {v: data[k] for k, v in mapping.items() if k in data}
