from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, String, select
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
