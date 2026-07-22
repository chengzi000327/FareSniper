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
        preferences = {
            "budget": result.budget if result is not None else None,
            "frequent_cities": result.frequent_cities or [] if result is not None else [],
            "preferred_airlines": result.preferred_airlines or [] if result is not None else [],
            "constraints": result.constraints or [] if result is not None else [],
            "travel_scenes": result.travel_scenes or [] if result is not None else [],
        }

        # User-confirmed values are stored as manual overrides. Merge them at
        # read time so later automatic learning cannot silently replace an
        # explicit correction made from the memory page.
        from backend.infrastructure.db.memory_repo import MemoryRow

        override_rows = (
            await self._s.execute(
                select(MemoryRow).where(
                    MemoryRow.user_id == user_id,
                    MemoryRow.field.in_(FIELD_LABELS),
                    MemoryRow.source.in_(("user", "manual")),
                )
            )
        ).scalars().all()
        for row in override_rows:
            preferences[row.field] = row.value

        return preferences if result is not None or override_rows else None

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
