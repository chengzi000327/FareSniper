from __future__ import annotations

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from backend.infrastructure.scrapers.multi_platform import scrape_all_routes


def build_scheduler() -> AsyncIOScheduler:
    s = AsyncIOScheduler(timezone="Asia/Shanghai")
    s.add_job(scrape_all_routes, trigger="cron", minute=5, id="hourly_scrape")
    return s
