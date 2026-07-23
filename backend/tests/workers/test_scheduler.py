from __future__ import annotations

import pytest

from backend.workers import run_all, scheduler as scheduler_module
from backend.workers.scheduler import build_scheduler


def test_hourly_scrape_job_registered_only_with_variflight_key(monkeypatch):
    monkeypatch.setattr(
        scheduler_module.settings, "variflight_api_key", "configured-key"
    )
    s = build_scheduler()
    job_ids = {j.id for j in s.get_jobs()}
    assert "hourly_scrape" in job_ids
    job = s.get_job("hourly_scrape")
    assert str(job.trigger).startswith("cron[")


def test_hourly_scrape_job_omitted_without_variflight_key(monkeypatch):
    monkeypatch.setattr(scheduler_module.settings, "variflight_api_key", "")

    scheduler = build_scheduler()

    assert scheduler.get_job("hourly_scrape") is None
    assert scheduler.get_job("ctrip_hourly_refresh") is not None


def test_ctrip_hourly_refresh_registered_at_minute_zero():
    scheduler = build_scheduler()

    job = scheduler.get_job("ctrip_hourly_refresh")

    assert job is not None
    assert "minute='0'" in str(job.trigger)
    assert job.max_instances == 1
    assert job.coalesce is True


@pytest.mark.asyncio
async def test_external_worker_registers_alert_and_notification_jobs(monkeypatch):
    scheduler = _FakeScheduler()
    monkeypatch.setattr(run_all, "build_scheduler", lambda: scheduler)
    monkeypatch.setattr(run_all.asyncio, "Event", _FinishedEvent)

    await run_all.main()

    assert scheduler.started is True
    assert scheduler.jobs == [
        (
            run_all.check_alerts_once,
            "interval",
            15,
            "alert_loop",
            {},
        ),
        (
            run_all.dispatch_notifications_once,
            "interval",
            1,
            "notification_dispatch",
            {"max_instances": 1, "coalesce": True},
        ),
    ]


class _FakeScheduler:
    def __init__(self):
        self.jobs = []
        self.started = False

    def add_job(self, func, trigger, *, minutes, id, **kwargs):
        self.jobs.append((func, trigger, minutes, id, kwargs))

    def start(self):
        self.started = True


class _FinishedEvent:
    async def wait(self):
        return None
