from __future__ import annotations

import pytest

from backend.application.graph.tools.set_alert import set_alert


@pytest.mark.asyncio
async def test_set_alert_creates_record(seeded_pg):
    out = await set_alert.ainvoke(
        {
            "origin": "BJS",
            "destination": "SYX",
            "depart_date": "2026-05-01",
            "target_price": 500,
            "injected_user_id": "u1",
        }
    )
    assert out["alert_id"].startswith("alert_")
    assert out["status"] == "active"


@pytest.mark.asyncio
async def test_missing_user_id_raises(seeded_pg):
    with pytest.raises(ValueError, match="_user_id required"):
        await set_alert.ainvoke(
            {
                "origin": "BJS",
                "destination": "SYX",
                "depart_date": "2026-05-01",
                "target_price": 500,
            }
        )
