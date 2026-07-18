from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from langsmith import Client, tracing_context

import backend.infrastructure.observability.provider_tracing as tracing
import backend.infrastructure.db.flight_snapshot_repo as snapshot_repo
from backend.application.contracts.flight_provider import ProviderStatus
from backend.application.services.flight_query import build_flight_query
from backend.data_sources.ctrip_source import CtripCollectionError
from backend.infrastructure.db.flight_demand_repo import (
    claim_due_demands,
    enqueue_demand,
)
from backend.infrastructure.flight_data.providers.ctrip_snapshot import (
    CtripSnapshotProvider,
)
from backend.workers.ctrip_refresh import (
    refresh_ctrip_once,
    seed_ctrip_demands,
    try_ctrip_worker_lease,
)


def _demand(
    origin: str = "BJS",
    destination: str = "SHA",
    depart_date: str = "2099-08-01",
) -> SimpleNamespace:
    return SimpleNamespace(
        origin_code=origin,
        destination_code=destination,
        depart_date=depart_date,
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

    async def record_upsert(provider, rows, ttl_minutes, **scope):
        calls.append((provider, rows, ttl_minutes, scope))

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
    assert source_kwargs == [
        {
            "enable_mock_fallback": False,
            "headless": True,
            "collection_timeout_seconds": 90.0,
        }
    ]


@pytest.mark.asyncio
async def test_successful_empty_refresh_replaces_the_route_inventory(monkeypatch):
    calls = []

    class EmptySource:
        async def search_flights(self, *args):
            return []

    async def record_upsert(provider, rows, ttl_minutes, **scope):
        calls.append((provider, rows, ttl_minutes, scope))

    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.try_ctrip_worker_lease", _acquired_lease
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.seed_ctrip_demands", _async_none
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.claim_due_demands",
        lambda limit: _async_value([_demand()]),
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.CtripSource", lambda **kwargs: EmptySource()
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.upsert_provider_flights", record_upsert
    )
    monkeypatch.setattr("backend.workers.ctrip_refresh.asyncio.sleep", _async_none)

    summary = await refresh_ctrip_once()

    assert summary.succeeded == 1
    assert calls == [
        (
            "ctrip_snapshot",
            [],
            75,
            {
                "origin_code": "BJS",
                "destination_code": "SHA",
                "depart_date": "2099-08-01",
            },
        )
    ]


@pytest.mark.asyncio
async def test_worker_empty_refresh_is_observed_by_provider_until_ttl_expires(
    seeded_pg,
    monkeypatch,
):
    observed_at = datetime(2099, 7, 1, 0, 0, tzinfo=timezone.utc)

    class FrozenDateTime(datetime):
        current = observed_at

        @classmethod
        def now(cls, tz=None):
            current = cls.current
            return current if tz is not None else current.replace(tzinfo=None)

    class EmptySource:
        async def search_flights(self, *args):
            return []

    queued = []

    async def capture_demand(**kwargs):
        queued.append(kwargs)

    monkeypatch.setattr(snapshot_repo, "datetime", FrozenDateTime)
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.try_ctrip_worker_lease", _acquired_lease
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.seed_ctrip_demands", _async_none
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.claim_due_demands",
        lambda limit: _async_value([_demand()]),
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.CtripSource", lambda **kwargs: EmptySource()
    )
    monkeypatch.setattr("backend.workers.ctrip_refresh.asyncio.sleep", _async_none)
    monkeypatch.setattr(
        "backend.infrastructure.flight_data.providers.ctrip_snapshot.enqueue_demand",
        capture_demand,
    )

    summary = await refresh_ctrip_once()
    query = build_flight_query("北京", "上海", "2099-08-01")
    fresh_empty = await CtripSnapshotProvider().search(query)

    assert summary.succeeded == 1
    assert fresh_empty.status is ProviderStatus.empty
    assert fresh_empty.cache_age_seconds == 0
    assert queued == []

    FrozenDateTime.current = observed_at + timedelta(minutes=76)
    expired_empty = await CtripSnapshotProvider().search(query)

    assert expired_empty.status is ProviderStatus.stale
    assert expired_empty.cache_age_seconds == 76 * 60
    assert len(queued) == 1


@pytest.mark.asyncio
async def test_overlap_skips_browser_and_seeding(monkeypatch, caplog):
    caplog.set_level("INFO", logger="backend.workers.ctrip_refresh")
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
async def test_refresh_wraps_each_demand_in_safe_child_span(monkeypatch):
    traced_demands = []

    class EmptySource:
        async def search_flights(self, *args):
            return []

    async def fake_trace_demand(
        *, origin_code, destination_code, depart_date, operation
    ):
        traced_demands.append((origin_code, destination_code, depart_date))
        return await operation()

    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.try_ctrip_worker_lease", _acquired_lease
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.seed_ctrip_demands", _async_none
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.claim_due_demands",
        lambda limit: _async_value(
            [_demand("BJS", "SHA"), _demand("CAN", "SHA")]
        ),
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.CtripSource",
        lambda **kwargs: EmptySource(),
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.trace_ctrip_demand",
        fake_trace_demand,
        raising=False,
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.upsert_provider_flights",
        _async_none,
    )
    monkeypatch.setattr("backend.workers.ctrip_refresh.asyncio.sleep", _async_none)

    summary = await refresh_ctrip_once()

    assert summary.processed == 2
    assert summary.succeeded == 2
    assert traced_demands == [
        ("BJS", "SHA", "2099-08-01"),
        ("CAN", "SHA", "2099-08-01"),
    ]


@pytest.mark.asyncio
async def test_refresh_cancellation_propagates_from_demand(monkeypatch):
    started = asyncio.Event()
    cancelled = asyncio.Event()

    class HangingSource:
        async def search_flights(self, *args):
            started.set()
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                cancelled.set()
                raise

    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.try_ctrip_worker_lease", _acquired_lease
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.seed_ctrip_demands", _async_none
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.claim_due_demands",
        lambda limit: _async_value([_demand()]),
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.CtripSource",
        lambda **kwargs: HangingSource(),
    )

    task = asyncio.create_task(refresh_ctrip_once())
    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled.is_set()


@pytest.mark.asyncio
async def test_refresh_counts_collection_error_and_continues_with_later_demand(
    monkeypatch, caplog
):
    caplog.set_level("INFO", logger="backend.workers.ctrip_refresh")
    sleeps = []
    persisted = []
    sentinel = "SENSITIVE_SENTINEL_DO_NOT_LOG"

    class PartiallyFailingSource:
        async def search_flights(self, origin, *args):
            if origin == "BJS":
                raise CtripCollectionError() from RuntimeError(sentinel)
            return [{"flight_no": "MU456", "prices": [{"platform": "携程", "price": 600}]}]

    async def fake_sleep(delay):
        sleeps.append(delay)

    async def fake_upsert(provider, rows, ttl_minutes, **scope):
        persisted.append((provider, rows, ttl_minutes, scope))

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
    assert (
        "ctrip_refresh_demand_failed origin=BJS destination=SHA "
        "depart_date=2099-08-01" in caplog.text
    )
    assert "ctrip_refresh_complete processed=2 succeeded=1 failed=1 skipped=0" in caplog.text
    assert sentinel not in caplog.text


@pytest.mark.asyncio
async def test_malicious_claimed_date_is_safely_failed_without_upstream_call(
    monkeypatch, caplog
):
    caplog.set_level("INFO", logger="backend.workers.ctrip_refresh")
    sentinel = "DATE_SECRET_SENTINEL in a complete malicious sentence"
    creates = []
    updates = []
    upstream_calls = []

    def capture_create(self, **kwargs):
        creates.append(kwargs)

    def capture_update(self, **kwargs):
        updates.append(kwargs)

    class FailIfCalledSource:
        async def search_flights(self, *args):
            upstream_calls.append(args)
            pytest.fail("invalid demand date reached the upstream source")

    monkeypatch.setattr(Client, "create_run", capture_create)
    monkeypatch.setattr(Client, "update_run", capture_update)
    monkeypatch.setattr(tracing, "langsmith_tracing_enabled", lambda: True)
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.try_ctrip_worker_lease", _acquired_lease
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.seed_ctrip_demands", _async_none
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.claim_due_demands",
        lambda limit: _async_value([_demand(depart_date=sentinel)]),
    )
    monkeypatch.setattr(
        "backend.workers.ctrip_refresh.CtripSource",
        lambda **kwargs: FailIfCalledSource(),
    )
    monkeypatch.setattr("backend.workers.ctrip_refresh.asyncio.sleep", _async_none)
    client = Client(
        api_url="https://langsmith.invalid",
        api_key="ls-test-key",
        auto_batch_tracing=False,
    )

    with tracing_context(
        enabled=True, client=client, project_name="task-10-worker-date-test"
    ):
        summary = await refresh_ctrip_once()

    assert summary.processed == 1
    assert summary.succeeded == 0
    assert summary.failed == 1
    assert upstream_calls == []
    demand_run = next(run for run in creates if run["name"] == "ctrip_demand")
    assert demand_run["inputs"] == {
        "origin_code": "BJS",
        "destination_code": "SHA",
        "depart_date_present": True,
    }
    trace_payload = repr((creates, updates))
    assert sentinel not in trace_payload
    assert "DATE_SECRET_SENTINEL" not in trace_payload
    assert "depart_date=<invalid>" in caplog.text
    assert sentinel not in caplog.text


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
