from __future__ import annotations

from backend.infrastructure.scrapers.base_scraper import ScrapeQuery
from backend.infrastructure.scrapers.ctrip_scraper import CtripScraper

_scraper = CtripScraper()


async def scrape_realtime(
    *, origin: str, destination: str, depart_date: str
) -> list[dict]:
    """Cache-miss fallback: query only the fastest single platform to stay under 3s."""
    return await _scraper.fetch(
        ScrapeQuery(origin=origin, destination=destination, depart_date=depart_date)
    )
