from __future__ import annotations

from sqlalchemy import select

from backend.db.models import SessionMeta
from backend.infrastructure.db.base import get_session


async def create_session_meta(
    session_id: str,
    user_id: str,
    slots: dict | None = None,
) -> SessionMeta:
    async with get_session() as s:
        row = SessionMeta(
            session_id=session_id,
            user_id=user_id,
            slots=slots or {},
        )
        s.add(row)
        await s.commit()
        await s.refresh(row)
        return row


async def get_session_meta(session_id: str) -> SessionMeta | None:
    async with get_session() as s:
        result = await s.execute(
            select(SessionMeta).where(SessionMeta.session_id == session_id)
        )
        return result.scalar_one_or_none()


async def touch_session(session_id: str, slots: dict | None = None) -> None:
    async with get_session() as s:
        result = await s.execute(
            select(SessionMeta).where(SessionMeta.session_id == session_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return
        if slots:
            row.slots = {**row.slots, **slots}
        row.turn_count += 1
        await s.commit()
