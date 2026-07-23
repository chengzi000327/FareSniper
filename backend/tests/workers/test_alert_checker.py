from __future__ import annotations

import pytest

from backend.infrastructure.db.alert_repo import create_alert, list_alerts
from backend.infrastructure.db.push_subscription_repo import upsert_subscription
from backend.workers.alert_checker import check_alerts_once


@pytest.mark.asyncio
async def test_alert_triggers_when_price_below_target(
    seeded_pg_with_low_price, fake_push
):
    aid = await create_alert(
        "u1",
        origin="BJS",
        destination="SYX",
        depart_date="2099-08-01",
        target_price=500,
    )
    await upsert_subscription(
        "u1",
        {
            "endpoint": "https://push.example/u1",
            "keys": {"p256dh": "p", "auth": "a"},
        },
    )
    await check_alerts_once()
    rows = await list_alerts("u1")
    assert any(a.id == aid and a.status == "triggered" for a in rows)
    assert fake_push.calls and fake_push.calls[0]["user_id"] == "u1"


@pytest.mark.asyncio
async def test_alert_triggers_without_subscription_but_does_not_send(
    seeded_pg_with_low_price, fake_push
):
    aid = await create_alert(
        "u2",
        origin="BJS",
        destination="SYX",
        depart_date="2099-08-01",
        target_price=500,
    )
    await check_alerts_once()
    rows = await list_alerts("u2")
    assert any(a.id == aid and a.status == "triggered" for a in rows)
    assert fake_push.calls == []
