from __future__ import annotations

import pytest

from backend.application.services.memory_learner import learn_from_search
from backend.infrastructure.db.memory_repo import list_memories


@pytest.mark.asyncio
async def test_learn_records_route_history(seeded_pg):
    await learn_from_search(
        "u1",
        origin="BJS",
        destination="SYX",
        depart_date="2026-05-01",
        picked_price=480,
    )
    rows = await list_memories("u1")
    fields = {m.field for m in rows}
    assert "frequent_routes" in fields
    assert "psychological_price_band" in fields
