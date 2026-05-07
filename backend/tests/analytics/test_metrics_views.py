"""Verify v_monthly_qpc and v_search_funnel views exist on the live DB.

The views use PostgreSQL-specific operators (FILTER, percentile_cont)
that SQLite can't emulate, so testing against ``seeded_pg`` is not
viable. The migration has been applied to Railway; we connect with the
existing ``db_engine`` fixture and assert structure.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_v_monthly_qpc_columns(db_engine):
    async with db_engine.connect() as conn:
        rows = await conn.execute(text("SELECT * FROM v_monthly_qpc LIMIT 0"))
        assert {"month_start", "qpc"}.issubset(set(rows.keys()))


@pytest.mark.asyncio
async def test_v_search_funnel_columns(db_engine):
    async with db_engine.connect() as conn:
        rows = await conn.execute(text("SELECT * FROM v_search_funnel LIMIT 0"))
        assert {
            "day",
            "search_count",
            "result_count",
            "click_count",
            "purchase_count",
        }.issubset(set(rows.keys()))
