from __future__ import annotations

import asyncio
from typing import Any

from backend.data_sources.normalizer import normalize_raw_rows
from backend.infrastructure.db.crawl_job_repo import (
    mark_crawl_job_failed,
    mark_crawl_job_success,
    start_crawl_job,
    update_platform_status,
)
from backend.infrastructure.db.flight_snapshot_repo import upsert_flights
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
        raw_rows = await scrape_route_all_platforms(
            origin=origin, destination=destination, depart_date=depart_date
        )
        valid_rows = [row for row in raw_rows if row.get("source") != "fake"]
        platform_status = _platform_status(raw_rows, valid_rows)
        await update_platform_status(job_id, platform_status)
        flights = normalize_raw_rows([_normalizer_row(row) for row in valid_rows])
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
    for origin, destination, depart_date in COVERED_ROUTES:
        await crawl_route(origin=origin, destination=destination, depart_date=depart_date)
