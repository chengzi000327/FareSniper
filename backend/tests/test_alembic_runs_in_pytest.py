"""Canonical schema regression for the launch plan.

The full canonical table set lands across TG-03, TG-04, TG-08, TG-09 and
TG-12 as repo modules and migrations get added. Until then this test is
expected to xfail: ``seeded_pg`` only knows about the four legacy tables
registered in ``backend.db.models``. Marking it ``xfail(strict=False)``
keeps it discoverable so that the day a TG completes its repo registry
the test flips to ``XPASSED`` and reminds us to drop the marker.
"""
from __future__ import annotations

import pytest
from sqlalchemy import inspect

CANONICAL_TABLES = {
    "analytics_events",
    "feature_flags",
    "cps_settlements",
    "flight_cache",
    "memories",
    "query_history",
    "users",
    "alerts",
    "push_subscriptions",
    "price_history",
    "promotions",
    "sessions_meta",
}


@pytest.mark.xfail(
    reason="canonical schema lands incrementally in TG-03/04/08/09/12; "
    "test flips to XPASSED once every repo module is registered",
    strict=False,
)
@pytest.mark.asyncio
async def test_all_target_tables_present(seeded_pg):
    async with seeded_pg.begin() as conn:
        names = await conn.run_sync(lambda c: inspect(c).get_table_names())
    missing = CANONICAL_TABLES - set(names)
    assert not missing, f"missing canonical tables: {sorted(missing)}"
