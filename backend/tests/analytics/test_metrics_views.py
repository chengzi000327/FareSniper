"""Verify v_monthly_qpc and v_search_funnel views exist on the test PG.

These views use PostgreSQL-only operators (FILTER, percentile_cont). Now
that ``seeded_pg`` connects to a real test PG (alembic head), we can
exercise them directly without falling back to production.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text


@pytest.mark.asyncio
async def test_v_monthly_qpc_columns(seeded_pg):
    async with seeded_pg.connect() as conn:
        rows = await conn.execute(text("SELECT * FROM v_monthly_qpc LIMIT 0"))
        assert {"month_start", "qpc"}.issubset(set(rows.keys()))


@pytest.mark.asyncio
async def test_v_search_funnel_columns(seeded_pg):
    async with seeded_pg.connect() as conn:
        rows = await conn.execute(text("SELECT * FROM v_search_funnel LIMIT 0"))
        assert {
            "day",
            "search_count",
            "result_count",
            "click_count",
            "purchase_count",
        }.issubset(set(rows.keys()))


@pytest.mark.asyncio
async def test_v_search_funnel_counts_each_event_type(seeded_pg):
    """Insert one of each tracked event and confirm the funnel splits them."""
    from backend.analytics.events import EventName
    from backend.analytics.track import track

    common = {"user_id": "u1"}
    await track(
        EventName.SEARCH_SUBMITTED,
        **common,
        payload={"query_text": "BJS->SYX", "user_id": "u1", "clarify_count": 0},
    )
    await track(
        EventName.RESULT_VIEWED,
        **common,
        payload={"result_count": 5, "has_signals": True, "has_preference": False},
    )
    await track(
        EventName.TICKET_CLICKED,
        **common,
        payload={
            "flight_no": "MU5137",
            "platform": "ctrip",
            "price": 480,
            "signals": ["历史低价"],
        },
    )
    await track(
        EventName.PURCHASE_JUMPED,
        **common,
        payload={"flight_no": "MU5137", "platform": "ctrip", "price": 480},
    )

    async with seeded_pg.connect() as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT search_count, result_count, click_count, purchase_count "
                    "FROM v_search_funnel"
                )
            )
        ).one()
    assert row.search_count == 1
    assert row.result_count == 1
    assert row.click_count == 1
    assert row.purchase_count == 1
