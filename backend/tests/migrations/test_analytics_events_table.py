"""Verify the analytics_events table is materialised on the test PG.

The schema is bootstrapped on the test PG via
``DATABASE_URL=$TEST_DATABASE_URL alembic -c backend/alembic.ini upgrade head``
once per environment; ``seeded_pg`` then truncates rows but leaves schema
intact for each test.
"""
from __future__ import annotations

import pytest
from sqlalchemy import inspect


EXPECTED_COLUMNS = {"id", "event_name", "user_id", "payload", "created_at"}


@pytest.mark.asyncio
async def test_analytics_events_columns(seeded_pg):
    async with seeded_pg.begin() as conn:
        cols = await conn.run_sync(
            lambda c: {col["name"] for col in inspect(c).get_columns("analytics_events")}
        )
    missing = EXPECTED_COLUMNS - cols
    assert not missing, f"missing columns on analytics_events: {sorted(missing)}"
