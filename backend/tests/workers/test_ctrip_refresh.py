from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

import backend.workers.ctrip_refresh as refresh_worker
from backend.workers.ctrip_refresh import (
    refresh_ctrip_once,
    seed_ctrip_demands,
    try_ctrip_worker_lease,
)


@pytest.mark.asyncio
async def test_railway_refresh_only_seeds_collector_queue(monkeypatch):
    async def seeded_count():
        return 4

    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.try_ctrip_worker_lease",
        _acquired_lease,
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.seed_ctrip_demands",
        seeded_count,
    )
    monkeypatch.setattr(
        refresh_worker,
        "claim_due_demands",
        lambda *args, **kwargs: pytest.fail(
            "Railway worker must not consume collector jobs"
        ),
        raising=False,
    )
    monkeypatch.setattr(
        refresh_worker,
        "CtripSource",
        lambda *args, **kwargs: pytest.fail(
            "Railway worker must not construct a browser source"
        ),
        raising=False,
    )

    summary = await refresh_ctrip_once()

    assert summary.processed == 4
    assert summary.succeeded == 4
    assert summary.failed == 0


def test_railway_worker_exports_no_browser_or_unowned_claim_path():
    assert not hasattr(refresh_worker, "CtripSource")
    assert not hasattr(refresh_worker, "claim_due_demands")


@asynccontextmanager
async def _acquired_lease():
    yield True


@asynccontextmanager
async def _rejected_lease():
    yield False


@pytest.mark.asyncio
async def test_overlap_skips_seeding(monkeypatch, caplog):
    caplog.set_level("INFO", logger="backend.workers.ctrip_refresh")
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.try_ctrip_worker_lease", _rejected_lease
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.seed_ctrip_demands",
        lambda: pytest.fail("overlap must skip demand seeding"),
    )
    summary = await refresh_ctrip_once()

    assert summary.skipped_overlap is True
    assert summary.processed == 0
    assert "ctrip_refresh_complete processed=0 succeeded=0 failed=0 skipped=1" in caplog.text


@pytest.mark.asyncio
async def test_refresh_runs_batch_inside_ctrip_root_trace(monkeypatch):
    traced_operations = []

    async def fake_trace_ctrip_refresh(operation):
        traced_operations.append(operation)
        return await operation()

    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.trace_ctrip_refresh",
        fake_trace_ctrip_refresh,
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.try_ctrip_worker_lease", _rejected_lease
    )

    summary = await refresh_ctrip_once()

    assert summary.skipped_overlap is True
    assert [operation.__name__ for operation in traced_operations] == [
        "_refresh_ctrip_once"
    ]


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
        "reactivate_completed": False,
    }
    hot_calls = calls[1:]
    assert len(hot_calls) == 3
    assert all(call["priority"] == 5 for call in hot_calls)
    assert all(call["source"] == "hot_route" for call in hot_calls)
    assert all(call["reactivate_completed"] is False for call in hot_calls)
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    assert all(call["depart_date"] > today.isoformat() for call in hot_calls)


@pytest.mark.asyncio
async def test_seed_skips_same_day_alert_and_keeps_future_alert(monkeypatch):
    calls = []
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()

    async def fake_enqueue(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.list_active_alert_routes",
        lambda: _async_value(
            [("北京", "上海", today), ("广州", "上海", "2099-08-02")]
        ),
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.enqueue_demand", fake_enqueue
    )
    monkeypatch.setattr("backend.workers.ctrip_refresh.HOT_ROUTES", [])

    seeded = await seed_ctrip_demands()

    assert seeded == 1
    assert calls == [
        {
            "origin_code": "CAN",
            "destination_code": "SHA",
            "depart_date": "2099-08-02",
            "priority": 100,
            "source": "price_alert",
            "reactivate_completed": False,
        }
    ]


@pytest.mark.asyncio
async def test_hot_route_seed_converts_catalog_locations_to_ctrip_codes(monkeypatch):
    calls = []

    async def fake_enqueue(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.list_active_alert_routes",
        lambda: _async_value([]),
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.enqueue_demand", fake_enqueue
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.HOT_ROUTES",
        [("北京大兴机场", "臺北")],
    )

    await seed_ctrip_demands()

    assert len(calls) == 3
    assert {call["origin_code"] for call in calls} == {"BJS"}
    assert {call["destination_code"] for call in calls} == {"TPE"}


@pytest.mark.asyncio
async def test_seed_skips_malicious_alert_and_continues_all_routes(
    monkeypatch, caplog
):
    caplog.set_level("WARNING", logger="backend.workers.ctrip_refresh")
    sentinel = "DATE_SECRET_SENTINEL in a complete malicious sentence"
    calls = []

    async def fake_enqueue(**kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.list_active_alert_routes",
        lambda: _async_value(
            [
                ("北京", "上海", sentinel),
                ("广州", "上海", "2099-08-02"),
            ]
        ),
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.enqueue_demand", fake_enqueue
    )
    monkeypatch.setattr("backend.workers.ctrip_refresh.HOT_ROUTES", [("BJS", "SYX")])

    await seed_ctrip_demands()

    assert len(calls) == 4
    assert calls[0] == {
        "origin_code": "CAN",
        "destination_code": "SHA",
        "depart_date": "2099-08-02",
            "priority": 100,
            "source": "price_alert",
            "reactivate_completed": False,
        }
    assert [call["source"] for call in calls[1:]] == ["hot_route"] * 3
    assert sentinel not in repr(calls)
    assert sentinel not in caplog.text
    assert "depart_date=<invalid>" in caplog.text


@pytest.mark.asyncio
async def test_seed_continues_after_expected_enqueue_rejection(monkeypatch, caplog):
    caplog.set_level("WARNING", logger="backend.workers.ctrip_refresh")
    calls = []

    async def fake_enqueue(**kwargs):
        if kwargs["source"] == "price_alert" and kwargs["origin_code"] == "BJS":
            raise ValueError("fixed enqueue rejection")
        calls.append(kwargs)

    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.list_active_alert_routes",
        lambda: _async_value(
            [
                ("北京", "上海", "2099-08-01"),
                ("广州", "上海", "2099-08-02"),
            ]
        ),
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.enqueue_demand", fake_enqueue
    )
    monkeypatch.setattr("backend.workers.ctrip_refresh.HOT_ROUTES", [("BJS", "SYX")])

    await seed_ctrip_demands()

    assert len(calls) == 4
    assert calls[0]["origin_code"] == "CAN"
    assert [call["source"] for call in calls[1:]] == ["hot_route"] * 3
    assert "reason=rejected" in caplog.text


@pytest.mark.asyncio
async def test_seed_propagates_unexpected_enqueue_failure(monkeypatch):
    async def fail_enqueue(**kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.list_active_alert_routes",
        lambda: _async_value([("北京", "上海", "2099-08-01")]),
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.enqueue_demand", fail_enqueue
    )

    with pytest.raises(RuntimeError, match="database unavailable"):
        await seed_ctrip_demands()


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
