from __future__ import annotations

import pytest

from backend.infrastructure.db.alert_repo import (
    create_alert,
    list_alerts,
    mark_triggered,
)


@pytest.mark.asyncio
async def test_create_then_list(seeded_pg):
    aid = await create_alert(
        "u1",
        origin="BJS",
        destination="SYX",
        depart_date="2026-05-01",
        target_price=500,
    )
    rows = await list_alerts("u1")
    assert any(a.id == aid for a in rows)


@pytest.mark.asyncio
async def test_mark_triggered_changes_status(seeded_pg):
    aid = await create_alert(
        "u1",
        origin="BJS",
        destination="SYX",
        depart_date="2026-05-01",
        target_price=500,
    )
    await mark_triggered(aid)
    rows = await list_alerts("u1")
    assert any(a.status == "triggered" for a in rows if a.id == aid)
