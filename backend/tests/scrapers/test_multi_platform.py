from __future__ import annotations

import pytest

from backend.infrastructure.db.flight_cache import read_cached_deals
from backend.infrastructure.scrapers.multi_platform import (
    scrape_all_routes,
    scrape_route_all_platforms,
)


@pytest.mark.asyncio
async def test_scrape_route_aggregates_5_platforms(stub_playwright):
    deals = await scrape_route_all_platforms(
        origin="BJS", destination="SHA", depart_date="2026-05-08"
    )
    platforms = {d["platform"] for d in deals}
    assert platforms == {"ctrip", "qunar", "tongcheng", "fliggy", "umetrip"}
    assert all(d.get("source") == "fake" for d in deals)


@pytest.mark.asyncio
async def test_scrape_all_routes_skips_fake_source(seeded_pg, stub_playwright):
    """Placeholder deals (source='fake') must not be written to flight_cache."""
    await scrape_all_routes()
    cached = await read_cached_deals(
        origin="BJS", destination="SHA", depart_date="2026-05-08"
    )
    assert cached == []


@pytest.mark.asyncio
async def test_scrape_all_routes_writes_real_source(seeded_pg, monkeypatch):
    """Real deals (source='scrape') must be written to flight_cache."""
    real_deals = [
        {
            "flight_no": "MU5137",
            "price": 480,
            "platform": "ctrip",
            "airline": "MU",
            "depart_time": "08:30",
            "arrive_time": "11:00",
            "origin": "BJS",
            "destination": "SHA",
            "depart_date": "2026-05-08",
            "source": "scrape",
        }
    ]

    async def fake_route(*, origin, destination, depart_date):
        if (origin, destination, depart_date) == ("BJS", "SHA", "2026-05-08"):
            return real_deals
        return []

    monkeypatch.setattr(
        "backend.infrastructure.scrapers.multi_platform.scrape_route_all_platforms",
        fake_route,
    )
    await scrape_all_routes()
    cached = await read_cached_deals(
        origin="BJS", destination="SHA", depart_date="2026-05-08"
    )
    assert cached and cached[0]["flight_no"] == "MU5137"
