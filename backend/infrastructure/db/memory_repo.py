from __future__ import annotations

from sqlalchemy import Column, DateTime, JSON, String, delete, select
from sqlalchemy.sql import func

from backend.db.models import UserPreference
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


async def upsert_preference_override(
    user_id: str, field: str, value: object
) -> None:
    """Persist a user-confirmed preference for both UI and Agent consumption.

    ``user_preferences`` is the source read by the Agent during matching and
    recommendation. ``memories`` keeps the per-field manual source marker so
    the memory page can explain that the value was confirmed by the user.
    """
    async with get_session() as s:
        preference = await s.get(UserPreference, user_id)
        if preference is None:
            preference = UserPreference(id=user_id)
            s.add(preference)
        setattr(preference, field, value)

        memory = (
            await s.execute(
                select(MemoryRow).where(
                    MemoryRow.user_id == user_id, MemoryRow.field == field
                )
            )
        ).scalar_one_or_none()
        if memory is None:
            s.add(
                MemoryRow(
                    user_id=user_id,
                    field=field,
                    value=value,
                    source="user",
                )
            )
        else:
            memory.value = value
            memory.source = "user"
        await s.commit()


async def list_memories(user_id: str) -> list[MemoryRow]:
    async with get_session() as s:
        rows = await s.execute(
            select(MemoryRow).where(MemoryRow.user_id == user_id)
        )
        return list(rows.scalars().all())


async def get_user_preferences(user_id: str) -> dict[str, object] | None:
    """Return the automatically learned preference row in API-ready form."""
    async with get_session() as s:
        row = await s.get(UserPreference, user_id)
        if row is None:
            return None
        return {
            "budget": row.budget,
            "frequent_cities": list(row.frequent_cities or []),
            "preferred_airlines": list(row.preferred_airlines or []),
            "constraints": list(row.constraints or []),
            "travel_scenes": list(row.travel_scenes or []),
        }


async def delete_field(user_id: str, field: str) -> None:
    async with get_session() as s:
        await s.execute(
            delete(MemoryRow).where(
                MemoryRow.user_id == user_id, MemoryRow.field == field
            )
        )
        await s.commit()


async def clear_preference_override(user_id: str, field: str) -> None:
    """Forget a preference from both the Agent table and the UI override."""
    async with get_session() as s:
        preference = await s.get(UserPreference, user_id)
        if preference is not None:
            setattr(preference, field, None if field == "budget" else [])
        await s.execute(
            delete(MemoryRow).where(
                MemoryRow.user_id == user_id, MemoryRow.field == field
            )
        )
        await s.commit()
