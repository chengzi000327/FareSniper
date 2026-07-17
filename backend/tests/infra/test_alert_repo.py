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
        depart_date="2099-08-01",
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
        depart_date="2099-08-01",
        target_price=500,
    )
    await mark_triggered(aid)
    rows = await list_alerts("u1")
    assert any(a.status == "triggered" for a in rows if a.id == aid)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "depart_date",
    [
        "2099-02-30",
        "2099-8-01",
        "DATE_SECRET_SENTINEL in a complete malicious sentence",
    ],
)
async def test_create_alert_rejects_invalid_date_without_persisting(
    seeded_pg, depart_date
):
    with pytest.raises(ValueError, match="valid YYYY-MM-DD") as exc_info:
        await create_alert(
            "u1",
            origin="BJS",
            destination="SYX",
            depart_date=depart_date,
            target_price=500,
        )

    assert depart_date not in str(exc_info.value)
    assert await list_alerts("u1") == []
