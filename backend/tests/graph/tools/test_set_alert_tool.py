from __future__ import annotations

import pytest

from backend.application.graph.tools.set_alert import set_alert
from backend.infrastructure.db.alert_repo import list_alerts


@pytest.mark.asyncio
async def test_set_alert_creates_record(seeded_pg):
    out = await set_alert.ainvoke(
        {
            "origin": "BJS",
            "destination": "SYX",
            "depart_date": "2099-08-01",
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
                "depart_date": "2099-08-01",
                "target_price": 500,
            }
        )


@pytest.mark.asyncio
async def test_set_alert_rejects_malicious_date_without_persisting(seeded_pg):
    sentinel = "DATE_SECRET_SENTINEL in a complete malicious sentence"

    with pytest.raises(ValueError, match="valid YYYY-MM-DD") as exc_info:
        await set_alert.ainvoke(
            {
                "origin": "BJS",
                "destination": "SYX",
                "depart_date": sentinel,
                "target_price": 500,
                "injected_user_id": "u1",
            }
        )

    assert sentinel not in str(exc_info.value)
    assert await list_alerts("u1") == []
