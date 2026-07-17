from __future__ import annotations

import pytest

from backend.infrastructure.db.flight_demand_repo import (
    claim_due_demands,
    enqueue_demand,
)


@pytest.mark.asyncio
async def test_enqueue_is_idempotent_and_raises_priority(seeded_pg):
    await enqueue_demand(
        origin_code="BJS",
        destination_code="SHA",
        depart_date="2099-08-01",
        priority=10,
        source="recent_search",
    )
    await enqueue_demand(
        origin_code="BJS",
        destination_code="SHA",
        depart_date="2099-08-01",
        priority=100,
        source="price_alert",
    )

    rows = await claim_due_demands(limit=10)

    assert len(rows) == 1
    assert rows[0].priority == 100
    assert rows[0].source == "price_alert"


@pytest.mark.asyncio
async def test_claim_schedules_next_collection_one_hour_later(seeded_pg):
    await enqueue_demand(
        origin_code="BJS",
        destination_code="SHA",
        depart_date="2099-08-01",
        priority=50,
        source="recent_search",
    )

    first_claim = await claim_due_demands(limit=10)
    second_claim = await claim_due_demands(limit=10)

    assert len(first_claim) == 1
    assert second_claim == []
