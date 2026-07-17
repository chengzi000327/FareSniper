from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.infrastructure.scrapers.multi_platform import scrape_all_routes
from backend.workers.ctrip_refresh import refresh_ctrip_once


def build_scheduler() -> AsyncIOScheduler:
    s = AsyncIOScheduler(timezone="Asia/Shanghai")
    s.add_job(scrape_all_routes, trigger="cron", minute=5, id="hourly_scrape")
    s.add_job(
        refresh_ctrip_once,
        trigger="cron",
        minute=0,
        id="ctrip_hourly_refresh",
        max_instances=1,
        coalesce=True,
    )
    return s
