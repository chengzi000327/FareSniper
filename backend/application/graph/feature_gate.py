"""Graph-time gates for the three PRD §4.2 differentiation flags.

Each helper combines two checks:
1. ``feature_flags.enabled`` row in PG (operational kill switch).
2. ``in_rollout`` deterministic per-user bucketing (gradual ramp).

Both must be true for the flag to take effect, so a flag set at
``enabled=True, rollout_pct=10`` exposes 10% of users; flipping
``enabled`` to false is an instant kill switch independent of rollout.
"""
from __future__ import annotations

from sqlalchemy import select

from backend.infrastructure.db.base import get_session
from backend.infrastructure.db.feature_flag_repo import FeatureFlag
from backend.infrastructure.flags.rollout import in_rollout


async def _gate(flag: str, user_id: str) -> bool:
    async with get_session() as session:
        row = (
            await session.execute(select(FeatureFlag).where(FeatureFlag.name == flag))
        ).scalar_one_or_none()
        if row is None or not row.enabled:
            return False
        return in_rollout(user_id, flag, row.rollout_pct)


async def should_run_value_judge(user_id: str) -> bool:
    """Whether to invoke the LLM-based ValueJudge for this user."""
    return await _gate("ai_value_judge", user_id)


async def should_aggregate_platforms(user_id: str) -> bool:
    """Whether to fan out across multi-platform scrapers vs single source."""
    return await _gate("multi_platform_aggregation", user_id)


async def should_use_memory(user_id: str) -> bool:
    """Whether to enrich the search with persisted preference memory."""
    return await _gate("preference_memory", user_id)
