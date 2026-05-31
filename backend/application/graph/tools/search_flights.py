from __future__ import annotations

import logging

from langchain_core.tools import tool

from backend.config import settings
from backend.data_sources.mock_flights import get_mock_flights
from backend.infrastructure.db.flight_snapshot_repo import read_deals
from backend.infrastructure.flight_data.variflight_client import search_flights as variflight_search

logger = logging.getLogger("faresniper.graph.tools.search_flights")


@tool
async def search_flights(origin: str, destination: str, depart_date: str) -> dict:
    """查询航班价格：优先读快照缓存，缓存空时调飞常准实时数据，最后 mock 兜底。"""
    # 1. 快照缓存
    try:
        deals = await read_deals(
            origin_code=origin, destination_code=destination, depart_date=depart_date
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

    # 2. 飞常准实时数据
    try:
        deals = await variflight_search(
            origin=origin, destination=destination, depart_date=depart_date
        )
    except Exception:
        logger.exception(
            "variflight_search_failed origin=%s destination=%s depart_date=%s",
            origin,
            destination,
            depart_date,
        )
        deals = []
    if deals:
        return {"deals": deals, "source": "variflight"}

    # 3. Mock 兜底（feature flag 控制）
    if settings.enable_mock_fallback:
        return {
            "deals": get_mock_flights(origin, destination, depart_date),
            "source": "mock_fallback",
        }
    return {"deals": [], "source": "empty"}
