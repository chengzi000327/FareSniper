from __future__ import annotations

import pytest

from backend.infrastructure.scrapers.realtime_fallback import scrape_realtime


@pytest.mark.asyncio
async def test_realtime_returns_subset_of_platforms(stub_playwright):
    """实时兜底走单平台（最快的 ctrip）以满足 < 3s 响应。"""
    deals = await scrape_realtime(
        origin="XIY", destination="URC", depart_date="2026-05-08"
    )
    assert deals
    assert all(d["platform"] == "ctrip" for d in deals)
