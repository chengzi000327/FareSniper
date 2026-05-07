from __future__ import annotations

import pytest

from backend.infrastructure.db.cps_settlement_repo import (
    get_settlement,
    upsert_settlement,
)


@pytest.mark.asyncio
async def test_upsert_then_get(seeded_pg):
    await upsert_settlement(
        order_id="CPS_20260507_1",
        platform="ctrip",
        user_id="u1",
        price=480,
        commission=24.0,
        status="paid",
    )
    row = await get_settlement("CPS_20260507_1")
    assert row.platform == "ctrip"
    assert row.user_id == "u1"
    assert row.price == 480
    assert row.commission == 24.0
    assert row.status == "paid"


@pytest.mark.asyncio
async def test_upsert_overwrites_status_and_commission(seeded_pg):
    await upsert_settlement(
        order_id="CPS_X",
        platform="qunar",
        user_id="u2",
        price=600,
        commission=18.0,
        status="pending",
    )
    await upsert_settlement(
        order_id="CPS_X",
        platform="qunar",
        user_id="u2",
        price=600,
        commission=22.5,
        status="paid",
    )
    row = await get_settlement("CPS_X")
    assert row.status == "paid"
    assert row.commission == 22.5


@pytest.mark.asyncio
async def test_get_settlement_raises_when_missing(seeded_pg):
    from sqlalchemy.exc import NoResultFound

    with pytest.raises(NoResultFound):
        await get_settlement("does-not-exist")
