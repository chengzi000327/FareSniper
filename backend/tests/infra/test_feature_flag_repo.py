from __future__ import annotations

import pytest

from backend.infrastructure.db.feature_flag_repo import is_enabled, set_flag


@pytest.mark.asyncio
async def test_default_disabled(seeded_pg):
    assert await is_enabled("ai_value_judge") is False


@pytest.mark.asyncio
async def test_set_then_read(seeded_pg):
    await set_flag("ai_value_judge", True, rollout_pct=100)
    assert await is_enabled("ai_value_judge") is True


@pytest.mark.asyncio
async def test_set_overwrites_existing(seeded_pg):
    await set_flag("ai_value_judge", True, rollout_pct=100)
    await set_flag("ai_value_judge", False, rollout_pct=0)
    assert await is_enabled("ai_value_judge") is False


@pytest.mark.asyncio
async def test_set_creates_when_missing(seeded_pg):
    assert await is_enabled("brand_new_flag") is False
    await set_flag("brand_new_flag", True, rollout_pct=50)
    assert await is_enabled("brand_new_flag") is True
