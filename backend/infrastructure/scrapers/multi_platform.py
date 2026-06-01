from __future__ import annotations

import asyncio
from datetime import date, timedelta
from typing import Any

from backend.config import settings
from backend.data_sources.normalizer import normalize_raw_rows
from backend.infrastructure.db.crawl_job_repo import (
    mark_crawl_job_failed,
    mark_crawl_job_success,
    start_crawl_job,
    update_platform_status,
)
from backend.infrastructure.db.flight_snapshot_repo import upsert_flights
from backend.infrastructure.flight_data.variflight_client import (
    search_flights as variflight_search,
)
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

# Playwright scrapers are disabled by default on Railway (headless browser unavailable).
# Set SCRAPER_PLAYWRIGHT_ENABLED=true in env to re-enable cross-platform cross-checking.
_PLAYWRIGHT_ENABLED = getattr(settings, "scraper_playwright_enabled", False)

# 北京出发热门航线（国内高频 OD 对）
_BJS_HOT_ROUTES = [
    ("BJS", "SHA"),  # 北京→上海
    ("BJS", "SYX"),  # 北京→三亚
    ("BJS", "CTU"),  # 北京→成都
    ("BJS", "CAN"),  # 北京→广州
    ("BJS", "XMN"),  # 北京→厦门
]


def _near_dates(days: int = 3) -> list[str]:
    """返回从明天起共 days 天的日期字符串列表（YYYY-MM-DD）。"""
    today = date.today()
    return [(today + timedelta(days=i + 1)).strftime("%Y-%m-%d") for i in range(days)]


def _build_covered_routes() -> list[tuple[str, str, str]]:
    """按最近 3 天动态生成路线×日期组合。"""
    dates = _near_dates(3)
    return [(orig, dest, d) for orig, dest in _BJS_HOT_ROUTES for d in dates]


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


def _normalizer_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "flight_number": row.get("flight_number") or row.get("flight_no", ""),
        "airline": row.get("airline", ""),
        "dep_city": row.get("dep_city") or row.get("origin", ""),
        "arr_city": row.get("arr_city") or row.get("destination", ""),
        "dep_time": row.get("dep_time") or row.get("depart_time", ""),
        "arr_time": row.get("arr_time") or row.get("arrive_time", ""),
        "duration": row.get("duration", ""),
        "transfer_count": row.get("transfer_count", 0),
        "price": row.get("price"),
        "date": row.get("date") or row.get("depart_date", ""),
        "platform": row.get("platform", ""),
        "url": row.get("url", ""),
    }


def _platform_status(rows: list[dict[str, Any]], valid_rows: list[dict[str, Any]]) -> dict[str, Any]:
    status: dict[str, Any] = {}
    for row in rows:
        platform = row.get("platform") or "unknown"
        item = status.setdefault(
            platform,
            {
                "status": "ok",
                "raw_rows": 0,
                "persisted_rows": 0,
                "skipped_fake_rows": 0,
            },
        )
        item["raw_rows"] += 1
        if row.get("source") == "fake":
            item["skipped_fake_rows"] += 1
    for row in valid_rows:
        platform = row.get("platform") or "unknown"
        item = status.setdefault(
            platform,
            {
                "status": "ok",
                "raw_rows": 0,
                "persisted_rows": 0,
                "skipped_fake_rows": 0,
            },
        )
        item["persisted_rows"] += 1
    for item in status.values():
        if item["persisted_rows"] == 0 and item["skipped_fake_rows"] > 0:
            item["status"] = "skipped_fake"
    return status


async def crawl_route(*, origin: str, destination: str, depart_date: str) -> str:
    job_id = await start_crawl_job(
        origin=origin, destination=destination, depart_date=depart_date
    )
    platform_status: dict[str, Any] = {}
    try:
        # 主数据源：飞常准
        variflight_rows = await variflight_search(
            origin=origin, destination=destination, depart_date=depart_date
        )

        # 可选：playwright OTA 爬虫（feature flag 默认关闭）
        playwright_rows: list[dict] = []
        if _PLAYWRIGHT_ENABLED:
            raw = await scrape_route_all_platforms(
                origin=origin, destination=destination, depart_date=depart_date
            )
            playwright_rows = [r for r in raw if r.get("source") != "fake"]

        all_valid = variflight_rows + playwright_rows
        platform_status = _platform_status(
            variflight_rows + playwright_rows, all_valid
        )
        await update_platform_status(job_id, platform_status)

        flights = normalize_raw_rows([_normalizer_row(r) for r in all_valid])
        if flights:
            await upsert_flights(flights)
        await mark_crawl_job_success(job_id, platform_status)
        return job_id
    except Exception as exc:
        await mark_crawl_job_failed(
            job_id, error_message=str(exc), platform_status=platform_status
        )
        raise


async def scrape_all_routes() -> None:
    for origin, destination, depart_date in _build_covered_routes():
        await crawl_route(origin=origin, destination=destination, depart_date=depart_date)
