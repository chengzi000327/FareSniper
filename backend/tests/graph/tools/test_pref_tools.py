from __future__ import annotations

import pytest

from backend.application.graph.tools.get_preferences import get_preferences
from backend.application.graph.tools.match_preferences import match_preferences


@pytest.mark.asyncio
async def test_get_preferences_reads_memories(seeded_pg_with_memory):
    out = await get_preferences.ainvoke({"user_id": "u1"})
    assert "budget_ceiling" in out
    assert out["budget_ceiling"] == 500


@pytest.mark.asyncio
async def test_match_preferences_filters_by_budget():
    deals = [{"flight_no": "MU1", "price": 380}, {"flight_no": "MU2", "price": 720}]
    pref = {"budget_ceiling": 500, "preferred_airlines": [], "constraints": []}
    out = await match_preferences.ainvoke({"deals": deals, "pref": pref})
    assert [d["flight_no"] for d in out["filtered"]] == ["MU1"]
