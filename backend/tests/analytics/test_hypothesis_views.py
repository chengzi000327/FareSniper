from __future__ import annotations

import pytest
from sqlalchemy import text

from backend.infrastructure.db.base import get_session


@pytest.mark.asyncio
async def test_h1_view_columns(seeded_pg):
    async with get_session() as s:
        r = await s.execute(text("SELECT * FROM v_h1_chat_vs_form LIMIT 1"))
        assert {"arm", "completion_rate"}.issubset(set(r.keys()))


@pytest.mark.asyncio
async def test_h2_adoption_rate_view(seeded_pg):
    async with get_session() as s:
        r = await s.execute(text("SELECT * FROM v_h2_advice_adoption LIMIT 1"))
        assert {"day", "adoption_rate"}.issubset(set(r.keys()))
