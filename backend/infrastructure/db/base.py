from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Base
from backend.db.session import AsyncSessionLocal as SessionLocal
from backend.db.session import engine

__all__ = ["Base", "SessionLocal", "engine", "get_session"]


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
