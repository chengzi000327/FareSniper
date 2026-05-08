from __future__ import annotations

from pathlib import Path

import pytest

from backend.infrastructure.scrapers.base_scraper import ScrapeQuery
from backend.infrastructure.scrapers.ctrip_scraper import CtripScraper
from backend.infrastructure.scrapers.fliggy_scraper import FliggyScraper
from backend.infrastructure.scrapers.qunar_scraper import QunarScraper
from backend.infrastructure.scrapers.tongcheng_scraper import TongchengScraper
from backend.infrastructure.scrapers.umetrip_scraper import UmetripScraper

FIXTURE_DIR = Path("backend/tests/fixtures/scrapers")

CASES = [
    (CtripScraper, "ctrip", "ctrip_flight_list.html"),
    (QunarScraper, "qunar", "qunar_flight_list.html"),
    (TongchengScraper, "tongcheng", "tongcheng_flight_list.html"),
    (FliggyScraper, "fliggy", "fliggy_flight_list.html"),
    (UmetripScraper, "umetrip", "umetrip_flight_list.html"),
]


@pytest.mark.parametrize("cls,platform,fixture_name", CASES)
def test_parse_real_fixture_returns_scrape_source(cls, platform, fixture_name):
    html = (FIXTURE_DIR / fixture_name).read_text()
    deals = cls()._parse(
        html, ScrapeQuery(origin="BJS", destination="SHA", depart_date="2026-05-08")
    )
    assert deals, f"{platform} fixture should produce at least one normalized deal"
    assert all(d["platform"] == platform for d in deals)
    assert all(d["source"] == "scrape" for d in deals), "real fixture must tag source=scrape"
    assert all(
        {"flight_no", "price", "airline", "depart_time", "arrive_time"} <= set(d)
        for d in deals
    )
