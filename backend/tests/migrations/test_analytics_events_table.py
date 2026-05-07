"""Verify the analytics_events table is materialised on the configured DB.

The ORM model that registers the table on ``Base.metadata`` lands in
TG-03 · Task 2 (``event_repo.py``); until then ``seeded_pg`` cannot
build the table on its SQLite copy. The migration itself, however, has
already been applied to the live Railway database, so this test simply
inspects the live engine and asserts the columns are present. Once
Task 2 introduces the ORM, ``seeded_pg`` will also pick the table up
and a parallel SQLite-backed assertion can be added.
"""
from __future__ import annotations

import pytest
from sqlalchemy import inspect


EXPECTED_COLUMNS = {"id", "event_name", "user_id", "payload", "created_at"}


@pytest.mark.asyncio
async def test_analytics_events_columns_on_live_db(db_engine):
    async with db_engine.begin() as conn:
        cols = await conn.run_sync(
            lambda c: {col["name"] for col in inspect(c).get_columns("analytics_events")}
        )
    missing = EXPECTED_COLUMNS - cols
    assert not missing, f"missing columns on analytics_events: {sorted(missing)}"
