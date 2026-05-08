from __future__ import annotations

import pytest

from backend.infrastructure.db.flight_cache import read_cached_deals, write_cached_deals


@pytest.mark.asyncio
async def test_roundtrip(seeded_pg):
    await write_cached_deals(
        origin="BJS",
        destination="SHA",
        depart_date="2026-05-08",
        deals=[{"flight_no": "MU5137", "price": 480, "platform": "ctrip"}],
    )
    rows = await read_cached_deals(
        origin="BJS", destination="SHA", depart_date="2026-05-08"
    )
    assert any(d["flight_no"] == "MU5137" for d in rows)
