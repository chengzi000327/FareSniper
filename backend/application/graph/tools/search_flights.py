from __future__ import annotations

from langchain_core.tools import tool

from backend.infrastructure.db.flight_cache import read_cached_deals
from backend.infrastructure.scrapers.realtime_fallback import scrape_realtime


@tool
async def search_flights(origin: str, destination: str, depart_date: str) -> dict:
    """读取航班价格缓存；若缓存为空，触发实时爬取兜底。"""
    deals = await read_cached_deals(
        origin=origin, destination=destination, depart_date=depart_date
    )
    if deals:
        return {"deals": deals, "source": "cache"}
    deals = await scrape_realtime(
        origin=origin, destination=destination, depart_date=depart_date
    )
    return {"deals": deals, "source": "realtime"}
