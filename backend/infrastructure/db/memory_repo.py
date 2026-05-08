from __future__ import annotations

from sqlalchemy import Column, DateTime, JSON, String, delete, select
from sqlalchemy.sql import func

from backend.infrastructure.db.base import Base, get_session


class MemoryRow(Base):
    __tablename__ = "memories"
    __table_args__ = {"extend_existing": True}

    user_id = Column(String, primary_key=True)
    field = Column(String, primary_key=True)
    value = Column(JSON, nullable=False)
    source = Column(String, nullable=False)
    updated_at = Column(DateTime, nullable=False, server_default=func.now())


async def upsert_memory(
    user_id: str, field: str, value: object, source: str = "learned"
) -> None:
    async with get_session() as s:
        row = (
            await s.execute(
                select(MemoryRow).where(
                    MemoryRow.user_id == user_id, MemoryRow.field == field
                )
            )
        ).scalar_one_or_none()
        if row is None:
            s.add(
                MemoryRow(user_id=user_id, field=field, value=value, source=source)
            )
        else:
            row.value = value
            row.source = source
        await s.commit()


async def list_memories(user_id: str) -> list[MemoryRow]:
    async with get_session() as s:
        rows = await s.execute(
            select(MemoryRow).where(MemoryRow.user_id == user_id)
        )
        return list(rows.scalars().all())


async def delete_field(user_id: str, field: str) -> None:
    async with get_session() as s:
        await s.execute(
            delete(MemoryRow).where(
                MemoryRow.user_id == user_id, MemoryRow.field == field
            )
        )
        await s.commit()
