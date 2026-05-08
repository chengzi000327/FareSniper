"""Verify that the enable_flags migration SQL sets the three flags to enabled.

Approach: seed the flags as disabled, replay the migration's UPDATE statement,
then confirm ``is_enabled`` returns True for each flag.  ``seeded_pg`` provides
an isolated test-PG engine with all rows pre-truncated.
"""
from __future__ import annotations

import pytest
from sqlalchemy import text

from backend.infrastructure.db.feature_flag_repo import is_enabled


@pytest.mark.asyncio
async def test_three_flags_enabled_after_migration(seeded_pg):
    # Insert flags as disabled (state before migration)
    async with seeded_pg.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO feature_flags (name, enabled, rollout_pct) VALUES "
                "('ai_value_judge', false, 0),"
                "('multi_platform_aggregation', false, 0),"
                "('preference_memory', false, 0)"
            )
        )

    # Replay migration upgrade SQL
    async with seeded_pg.begin() as conn:
        await conn.execute(
            text(
                "UPDATE feature_flags SET enabled = true, rollout_pct = 100 "
                "WHERE name IN ('ai_value_judge','multi_platform_aggregation','preference_memory')"
            )
        )

    assert await is_enabled("ai_value_judge") is True
    assert await is_enabled("multi_platform_aggregation") is True
    assert await is_enabled("preference_memory") is True
