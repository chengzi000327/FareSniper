from __future__ import annotations

import pytest

from backend.infrastructure.scrapers.base_scraper import ScrapeQuery
from backend.infrastructure.scrapers.ctrip_scraper import CtripScraper
from backend.infrastructure.scrapers.fliggy_scraper import FliggyScraper
from backend.infrastructure.scrapers.qunar_scraper import QunarScraper
from backend.infrastructure.scrapers.tongcheng_scraper import TongchengScraper
from backend.infrastructure.scrapers.umetrip_scraper import UmetripScraper

SCRAPERS = [
    (CtripScraper, "ctrip"),
    (QunarScraper, "qunar"),
    (TongchengScraper, "tongcheng"),
    (FliggyScraper, "fliggy"),
    (UmetripScraper, "umetrip"),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("cls,platform", SCRAPERS)
async def test_each_scraper_returns_normalized_deals(cls, platform, stub_playwright):
    deals = await cls().fetch(
        ScrapeQuery(origin="BJS", destination="SHA", depart_date="2026-05-08")
    )
    assert deals, f"{platform} should return at least one deal"
    assert all(d["platform"] == platform for d in deals)
    assert all({"flight_no", "price", "airline"} <= set(d) for d in deals)
    assert all(d.get("source") == "fake" for d in deals), "stub should tag source=fake"
