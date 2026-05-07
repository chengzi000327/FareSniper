from __future__ import annotations

import pytest
from sqlalchemy import text

from backend.db.models import Base as ExistingBase
from backend.infrastructure.db.base import Base, engine, get_session


def test_base_metadata_exposed():
    assert Base.metadata is not None
    assert Base is ExistingBase


def test_engine_is_async():
    assert engine is not None
    assert engine.url.drivername.startswith("postgresql+asyncpg") or engine.url.drivername.startswith("sqlite+aiosqlite")


@pytest.mark.asyncio
async def test_get_session_can_run_select_one():
    async with get_session() as s:
        result = await s.execute(text("SELECT 1"))
        assert result.scalar_one() == 1
