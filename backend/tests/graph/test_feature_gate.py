from __future__ import annotations

import pytest

from backend.application.graph.feature_gate import (
    should_aggregate_platforms,
    should_run_value_judge,
    should_use_memory,
)


@pytest.mark.asyncio
async def test_value_judge_skipped_when_flag_off(seeded_pg):
    assert await should_run_value_judge(user_id="u1") is False


@pytest.mark.asyncio
async def test_value_judge_enabled_when_flag_on(enable_flag):
    await enable_flag("ai_value_judge", rollout_pct=100)
    assert await should_run_value_judge(user_id="u1") is True


@pytest.mark.asyncio
async def test_value_judge_skipped_when_user_outside_rollout(enable_flag):
    await enable_flag("ai_value_judge", rollout_pct=0)
    assert await should_run_value_judge(user_id="u1") is False


@pytest.mark.asyncio
async def test_aggregate_platforms_gate(enable_flag):
    assert await should_aggregate_platforms(user_id="u1") is False
    await enable_flag("multi_platform_aggregation", rollout_pct=100)
    assert await should_aggregate_platforms(user_id="u1") is True


@pytest.mark.asyncio
async def test_use_memory_gate(enable_flag):
    assert await should_use_memory(user_id="u1") is False
    await enable_flag("preference_memory", rollout_pct=100)
    assert await should_use_memory(user_id="u1") is True
