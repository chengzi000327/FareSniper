from __future__ import annotations

import logging

from langchain_core.tools import tool

from backend.config import settings
from backend.data_sources.mock_flights import get_mock_flights
from backend.infrastructure.db.flight_cache import read_cached_deals
from backend.infrastructure.scrapers.realtime_fallback import scrape_realtime

logger = logging.getLogger("faresniper.graph.tools.search_flights")


@tool
async def search_flights(origin: str, destination: str, depart_date: str) -> dict:
    """读取航班价格缓存；若缓存为空，触发实时爬取兜底。"""
    try:
        deals = await read_cached_deals(
            origin=origin, destination=destination, depart_date=depart_date
        )
    except Exception:
        logger.exception(
            "flight_cache_read_failed origin=%s destination=%s depart_date=%s",
            origin,
            destination,
            depart_date,
        )
        deals = []
    if deals:
        return {"deals": deals, "source": "cache"}

    try:
        deals = await scrape_realtime(
            origin=origin, destination=destination, depart_date=depart_date
        )
    except Exception:
        logger.exception(
            "realtime_scrape_failed origin=%s destination=%s depart_date=%s",
            origin,
            destination,
            depart_date,
        )
        deals = []
    if deals:
        return {"deals": deals, "source": "realtime"}

    if settings.enable_mock_fallback:
        return {
            "deals": get_mock_flights(origin, destination, depart_date),
            "source": "mock_fallback",
        }
    return {"deals": [], "source": "empty"}
