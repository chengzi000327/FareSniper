from __future__ import annotations

from sqlalchemy import select

from backend.db.models import QueryHistory as QueryHistoryRow
from backend.infrastructure.db.base import get_session


async def append_query(
    user_id: str, query_text: str, intent: dict | None = None
) -> None:
    async with get_session() as s:
        s.add(
            QueryHistoryRow(
                user_id=user_id,
                query_text=query_text,
                intent=intent or {},
            )
        )
        await s.commit()


async def list_query_history(
    user_id: str, limit: int = 20
) -> list[QueryHistoryRow]:
    async with get_session() as s:
        rows = await s.execute(
            select(QueryHistoryRow)
            .where(QueryHistoryRow.user_id == user_id)
            .order_by(
                QueryHistoryRow.created_at.desc(),
                QueryHistoryRow.id.desc(),
            )
            .limit(limit)
        )
        return list(rows.scalars().all())
