from __future__ import annotations

from backend.workers.scheduler import build_scheduler


def test_hourly_scrape_job_registered():
    s = build_scheduler()
    job_ids = {j.id for j in s.get_jobs()}
    assert "hourly_scrape" in job_ids
    job = s.get_job("hourly_scrape")
    assert str(job.trigger).startswith("cron[")
