from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from backend.infrastructure.db.flight_demand_repo import (
    claim_due_demands,
    enqueue_demand,
)
from backend.workers.ctrip_refresh import (
    refresh_ctrip_once,
    seed_ctrip_demands,
    try_ctrip_worker_lease,
)


def _demand(origin: str = "BJS", destination: str = "SHA") -> SimpleNamespace:
    return SimpleNamespace(
        origin_code=origin,
        destination_code=destination,
        depart_date="2099-08-01",
    )


@asynccontextmanager
async def _acquired_lease():
    yield True


@asynccontextmanager
async def _rejected_lease():
    yield False


@pytest.mark.asyncio
async def test_refresh_persists_real_ctrip_rows(monkeypatch):
    calls = []
    source_kwargs = []

    class FakeRealCtripSource:
        async def search_flights(self, *args):
            return [{"flight_no": "CA123", "prices": [{"platform": "携程", "price": 500}]}]

    async def record_upsert(provider, rows, ttl_minutes):
        calls.append((provider, rows, ttl_minutes))

    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.claim_due_demands",
        lambda limit: _async_value([_demand()]),
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.CtripSource",
        lambda **kwargs: source_kwargs.append(kwargs) or FakeRealCtripSource(),
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.upsert_provider_flights", record_upsert
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.try_ctrip_worker_lease", _acquired_lease
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.seed_ctrip_demands", _async_none
    )
    monkeypatch.setattr("backend.workers.ctrip_refresh.asyncio.sleep", _async_none)

    summary = await refresh_ctrip_once()

    assert summary.processed == 1
    assert summary.succeeded == 1
    assert calls[0][0] == "ctrip_snapshot"
    assert calls[0][2] == 75
    assert source_kwargs == [{"enable_mock_fallback": False, "headless": True}]


@pytest.mark.asyncio
async def test_overlap_skips_browser_and_seeding(monkeypatch):
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.try_ctrip_worker_lease", _rejected_lease
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.seed_ctrip_demands",
        lambda: pytest.fail("overlap must skip demand seeding"),
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.CtripSource",
        lambda **kwargs: pytest.fail("overlap must skip browser construction"),
    )

    summary = await refresh_ctrip_once()

    assert summary.skipped_overlap is True
    assert summary.processed == 0


@pytest.mark.asyncio
async def test_refresh_isolates_failures_and_delays_every_demand(monkeypatch):
    sleeps = []
    persisted = []

    class PartiallyFailingSource:
        async def search_flights(self, origin, *args):
            if origin == "BJS":
                raise RuntimeError("private browser payload")
            return [{"flight_no": "MU456", "prices": [{"platform": "携程", "price": 600}]}]

    async def fake_sleep(delay):
        sleeps.append(delay)

    async def fake_upsert(provider, rows, ttl_minutes):
        persisted.append((provider, rows, ttl_minutes))

    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.try_ctrip_worker_lease", _acquired_lease
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.seed_ctrip_demands", _async_none
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.claim_due_demands",
        lambda limit: _async_value([_demand("BJS", "SHA"), _demand("CAN", "SHA")]),
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.CtripSource",
        lambda **kwargs: PartiallyFailingSource(),
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.upsert_provider_flights", fake_upsert
    )
    monkeypatch.setattr("backend.workers.ctrip_refresh.asyncio.sleep", fake_sleep)

    summary = await refresh_ctrip_once()

    assert summary.processed == 2
    assert summary.succeeded == 1
    assert summary.failed == 1
    assert len(persisted) == 1
    assert len(sleeps) == 2
    assert all(2.0 <= delay <= 5.0 for delay in sleeps)


@pytest.mark.asyncio
async def test_acquired_lease_unlocks_even_when_body_raises(monkeypatch):
    session = _FakeLeaseSession(acquired=True)
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.get_session",
        lambda: _session_context(session),
    )

    with pytest.raises(RuntimeError, match="batch failed"):
        async with try_ctrip_worker_lease() as acquired:
            assert acquired is True
            raise RuntimeError("batch failed")

    assert session.scalar_calls == 1
    assert session.unlock_calls == 1


@pytest.mark.asyncio
async def test_seed_ctrip_demands_uses_alert_and_hot_route_priorities(monkeypatch):
    calls = []

    async def fake_enqueue(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.list_active_alert_routes",
        lambda: _async_value([("北京", "上海", "2099-08-01"), ("无效", "上海", "2099-08-02")]),
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.enqueue_demand", fake_enqueue
    )
    monkeypatch.setattr("backend.workers.ctrip_refresh.HOT_ROUTES", [("BJS", "SYX")])

    await seed_ctrip_demands()

    assert calls[0] == {
        "origin_code": "BJS",
        "destination_code": "SHA",
        "depart_date": "2099-08-01",
        "priority": 100,
        "source": "price_alert",
    }
    hot_calls = calls[1:]
    assert len(hot_calls) == 3
    assert all(call["priority"] == 5 for call in hot_calls)
    assert all(call["source"] == "hot_route" for call in hot_calls)
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    assert all(call["depart_date"] > today.isoformat() for call in hot_calls)


@pytest.mark.asyncio
async def test_claim_order_and_past_date_inactivation(seeded_pg):
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    demands = [
        ("BJS", "SHA", "2099-08-01", 5, "hot_route"),
        ("BJS", "CAN", "2099-08-01", 50, "recent_search"),
        ("BJS", "SYX", "2099-08-01", 100, "price_alert"),
        ("BJS", "XMN", today, 20, "same_day_search"),
        ("BJS", "CTU", "2000-01-01", 100, "price_alert"),
    ]
    for origin, destination, depart_date, priority, source in demands:
        await enqueue_demand(
            origin_code=origin,
            destination_code=destination,
            depart_date=depart_date,
            priority=priority,
            source=source,
        )

    claimed = await claim_due_demands(limit=10)

    assert [d.source for d in claimed] == [
        "price_alert",
        "recent_search",
        "same_day_search",
        "hot_route",
    ]
    assert all(d.depart_date != "2000-01-01" for d in claimed)


async def _async_none(*args, **kwargs):
    return None


async def _async_value(value):
    return value


class _FakeLeaseSession:
    def __init__(self, *, acquired: bool):
        self.acquired = acquired
        self.scalar_calls = 0
        self.unlock_calls = 0

    async def scalar(self, statement):
        self.scalar_calls += 1
        return self.acquired

    async def execute(self, statement):
        self.unlock_calls += 1


@asynccontextmanager
async def _session_context(session):
    yield session
