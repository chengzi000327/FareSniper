from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, String, delete, select, update
from sqlalchemy.sql import func

from backend.infrastructure.db.base import Base, get_session


class User(Base):
    __tablename__ = "users"
    __table_args__ = {"extend_existing": True}

    id = Column(String, primary_key=True)
    phone = Column(String, nullable=True, unique=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())


async def allocate_anonymous() -> str:
    uid = f"anon_{uuid.uuid4().hex[:16]}"
    async with get_session() as s:
        s.add(User(id=uid))
        await s.commit()
    return uid


async def link_phone(user_id: str, phone: str) -> User:
    async with get_session() as s:
        row = (
            await s.execute(select(User).where(User.id == user_id))
        ).scalar_one()
        row.phone = phone
        await s.commit()
        return row


async def find_or_create_by_phone(phone: str) -> User:
    """Reuse same user_id for repeated phone logins; create on first use."""
    async with get_session() as s:
        row = (
            await s.execute(select(User).where(User.phone == phone))
        ).scalar_one_or_none()
        if row is not None:
            return row
    uid = await allocate_anonymous()
    return await link_phone(uid, phone)


async def merge_anonymous_user(*, anon_id: str, target_id: str) -> None:
    """Migrate all data owned by anon_id into target_id, then delete anon user."""
    if anon_id == target_id:
        return
    from backend.infrastructure.db.memory_repo import MemoryRow
    from backend.infrastructure.db.query_history_repo import QueryHistoryRow

    async with get_session() as s:
        existing_fields = list(
            (
                await s.execute(
                    select(MemoryRow.field).where(MemoryRow.user_id == target_id)
                )
            ).scalars().all()
        )
        if existing_fields:
            await s.execute(
                delete(MemoryRow).where(
                    MemoryRow.user_id == anon_id,
                    MemoryRow.field.in_(existing_fields),
                )
            )
        await s.execute(
            update(MemoryRow)
            .where(MemoryRow.user_id == anon_id)
            .values(user_id=target_id)
        )
        await s.execute(
            update(QueryHistoryRow)
            .where(QueryHistoryRow.user_id == anon_id)
            .values(user_id=target_id)
        )
        try:
            from backend.infrastructure.db.alert_repo import PriceAlert

            await s.execute(
                update(PriceAlert)
                .where(PriceAlert.user_id == anon_id)
                .values(user_id=target_id)
            )
        except Exception:
            pass
        await s.execute(delete(User).where(User.id == anon_id))
        await s.commit()
