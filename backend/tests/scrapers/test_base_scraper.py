from __future__ import annotations

import pytest

from backend.infrastructure.scrapers.base_scraper import BaseScraper, ScrapeQuery


class _Dummy(BaseScraper):
    platform = "dummy"

    async def fetch(self, q: ScrapeQuery) -> list[dict]:
        return [{"flight_no": "XX001", "price": 100, "platform": self.platform}]


@pytest.mark.asyncio
async def test_dummy_scraper_returns_deals():
    deals = await _Dummy().fetch(
        ScrapeQuery(origin="BJS", destination="SHA", depart_date="2026-05-08")
    )
    assert len(deals) == 1
    assert deals[0]["platform"] == "dummy"
