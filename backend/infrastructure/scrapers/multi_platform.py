from __future__ import annotations

import asyncio

from backend.infrastructure.db.flight_cache import write_cached_deals
from backend.infrastructure.scrapers.base_scraper import ScrapeQuery
from backend.infrastructure.scrapers.ctrip_scraper import CtripScraper
from backend.infrastructure.scrapers.fliggy_scraper import FliggyScraper
from backend.infrastructure.scrapers.qunar_scraper import QunarScraper
from backend.infrastructure.scrapers.tongcheng_scraper import TongchengScraper
from backend.infrastructure.scrapers.umetrip_scraper import UmetripScraper

_ALL_SCRAPERS = [
    CtripScraper(),
    QunarScraper(),
    TongchengScraper(),
    FliggyScraper(),
    UmetripScraper(),
]

COVERED_ROUTES = [
    ("BJS", "SHA", "2026-05-08"),
    ("BJS", "SYX", "2026-05-01"),
    ("CAN", "HGH", "2026-05-08"),
    ("SHA", "CTU", "2026-05-08"),
    ("SZX", "XIY", "2026-05-08"),
]


async def scrape_route_all_platforms(
    *, origin: str, destination: str, depart_date: str
) -> list[dict]:
    q = ScrapeQuery(origin=origin, destination=destination, depart_date=depart_date)
    results = await asyncio.gather(
        *[s.fetch(q) for s in _ALL_SCRAPERS], return_exceptions=True
    )
    deals: list[dict] = []
    for r in results:
        if isinstance(r, Exception):
            continue
        deals.extend(r)
    return deals


async def scrape_all_routes() -> None:
    for origin, destination, depart_date in COVERED_ROUTES:
        deals = await scrape_route_all_platforms(
            origin=origin, destination=destination, depart_date=depart_date
        )
        if not deals:
            continue
        # Guard: if any deal carries source='fake' (placeholder branch), reject the
        # entire batch — placeholder data must never pollute flight_cache.
        if any(deal.get("source") == "fake" for deal in deals):
            continue
        await write_cached_deals(
            origin=origin, destination=destination, depart_date=depart_date, deals=deals
        )
