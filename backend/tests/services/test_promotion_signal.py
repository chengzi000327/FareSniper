import pytest
from backend.infrastructure.db.promotion_repo import upsert_promotion
from backend.application.services.promotion_signal import attach_promotion_signal


@pytest.mark.asyncio
async def test_signal_attached_when_promotion_active(seeded_pg):
    await upsert_promotion(
        platform="ctrip",
        flight_no="MU5137",
        date="2026-05-08",
        discount_pct=20,
        expires_at="2026-05-08T18:00:00Z",
    )
    deal = {"flight_no": "MU5137", "platform": "ctrip", "depart_date": "2026-05-08", "signals": []}
    out = await attach_promotion_signal(deal)
    assert "限时特卖" in out["signals"]
