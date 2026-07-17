from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest
from langsmith import Client, traceable, tracing_context

import backend.infrastructure.observability.provider_tracing as tracing
from backend.config import get_settings
from backend.application.contracts.decision import FrontendResponse
from backend.application.contracts.flight_provider import (
    FlightOffer,
    ProviderResult,
    ProviderStatus,
)
from backend.application.services.flight_query import build_flight_query
from backend.application.services.search_events import (
    SearchEventEmitter,
    bind_search_event_emitter,
)
from backend.workers.ctrip_refresh import CtripRefreshSummary


@dataclass
class _TraceRecord:
    name: str
    run_type: str
    inputs: dict[str, Any]
    parent: str | None
    outputs: dict[str, Any] | None = None
    exit_exception: BaseException | None = None
    end_calls: int = 0


class _FakeRun:
    def __init__(self, record: _TraceRecord) -> None:
        self._record = record

    def end(self, *, outputs: dict[str, Any]) -> None:
        self._record.end_calls += 1
        self._record.outputs = outputs


class _FakeTrace:
    def __init__(
        self,
        records: list[_TraceRecord],
        active: list[_TraceRecord],
        name: str,
        run_type: str,
        inputs: dict[str, Any],
    ) -> None:
        self._active = active
        self._record = _TraceRecord(
            name=name,
            run_type=run_type,
            inputs=inputs,
            parent=active[-1].name if active else None,
        )
        records.append(self._record)

    def __enter__(self) -> _FakeRun:
        self._active.append(self._record)
        return _FakeRun(self._record)

    def __exit__(self, exc_type, exc, traceback) -> None:
        self._record.exit_exception = exc
        assert self._active.pop() is self._record


@pytest.fixture
def trace_records(monkeypatch) -> list[_TraceRecord]:
    records: list[_TraceRecord] = []
    active: list[_TraceRecord] = []

    def fake_trace(
        name: str, run_type: str = "chain", *, inputs: dict[str, Any]
    ) -> _FakeTrace:
        return _FakeTrace(records, active, name, run_type, inputs)

    monkeypatch.setattr(tracing, "trace", fake_trace)
    monkeypatch.setattr(
        tracing, "langsmith_tracing_enabled", lambda: True, raising=False
    )
    return records


@pytest.fixture
def sdk_runs(monkeypatch):
    creates: list[dict[str, Any]] = []
    updates: list[dict[str, Any]] = []

    def capture_create(self, **kwargs):
        creates.append(kwargs)

    def capture_update(self, **kwargs):
        updates.append(kwargs)

    monkeypatch.setattr(Client, "create_run", capture_create)
    monkeypatch.setattr(Client, "update_run", capture_update)
    client = Client(
        api_url="https://langsmith.invalid",
        api_key="ls-test-key",
        auto_batch_tracing=False,
    )
    return client, creates, updates


def _offer() -> FlightOffer:
    return FlightOffer(
        data_provider="flyai",
        seller_name="secret seller",
        flight_no="CA1835",
        origin_city="北京",
        origin_code="BJS",
        destination_city="上海",
        destination_code="SHA",
        depart_date="2099-08-01",
        total_price=580,
        booking_url="https://book.example.test/path?api_key=must-not-leak",
        raw_reference="raw-provider-payload-must-not-leak",
    )


def test_safe_provider_inputs_and_outputs_are_summary_only():
    inputs = tracing.safe_provider_inputs(
        provider="flyai",
        origin_code="BJS",
        destination_code="SHA",
        depart_date="2099-08-01",
    )
    outputs = tracing.safe_provider_outputs(
        status="success",
        offer_count=3,
        latency_ms=420,
        cache_age_seconds=None,
    )

    assert inputs == {
        "provider": "flyai",
        "origin_code": "BJS",
        "destination_code": "SHA",
        "depart_date": "2099-08-01",
    }
    assert outputs == {
        "status": "success",
        "offer_count": 3,
        "latency_ms": 420,
        "cache_age_seconds": None,
    }
    assert "api_key" not in repr((inputs, outputs)).lower()


@pytest.mark.asyncio
async def test_flight_search_trace_tree_contains_only_safe_summaries(trace_records):
    query = build_flight_query("北京", "上海", "2099-08-01")
    provider_result = ProviderResult(
        provider="flyai",
        status=ProviderStatus.success,
        offers=[_offer()],
        latency_ms=420,
    )
    events: list[dict] = []

    async def search_operation() -> FrontendResponse:
        result = await tracing.trace_provider_call(
            "flyai", query, lambda: _async_value(provider_result)
        )
        normalized = tracing.trace_stage(
            "normalize_and_deduplicate",
            {
                "origin_code": query.origin_code,
                "destination_code": query.destination_code,
                "depart_date": query.depart_date,
                "result_count": len(result.offers),
                "raw_offer": result.offers[0],
                "booking_url": result.offers[0].booking_url,
            },
            lambda: [{"booking_url": result.offers[0].booking_url}],
        )
        tracing.trace_stage(
            "rank_results",
            {"result_count": len(normalized)},
            lambda: normalized,
        )
        return FrontendResponse(
            user_id="u1",
            session_id="s1",
            deals=normalized,
            analysis={},
            recommendation={},
            meta={},
        )

    with bind_search_event_emitter(SearchEventEmitter("req-1", events.append)):
        response = await tracing.trace_flight_search(
            "req-1", len("北京到上海"), search_operation
        )

    assert response.session_id == "s1"
    assert [record.name for record in trace_records] == [
        "flight_search",
        "provider.flyai",
        "normalize_and_deduplicate",
        "rank_results",
        "stream_results",
    ]
    assert trace_records[0].parent is None
    assert all(record.parent == "flight_search" for record in trace_records[1:])
    assert trace_records[0].inputs == {
        "request_id": "req-1",
        "message_length": len("北京到上海"),
    }
    assert trace_records[1].outputs == {
        "status": "success",
        "offer_count": 1,
        "latency_ms": 420,
        "cache_age_seconds": None,
    }
    assert trace_records[2].outputs == {"result_count": 1}
    assert trace_records[3].outputs == {"result_count": 1}
    assert trace_records[4].outputs == {"event_type": "complete"}
    assert trace_records[0].outputs == {
        "deal_count": 1,
        "has_recommendation": False,
    }
    assert [event["type"] for event in events] == ["complete"]

    trace_payload = repr(
        [(record.inputs, record.outputs) for record in trace_records]
    )
    assert "raw-provider-payload-must-not-leak" not in trace_payload
    assert "book.example.test" not in trace_payload
    assert "secret seller" not in trace_payload
    assert all(record.end_calls == 1 for record in trace_records)


@pytest.mark.asyncio
async def test_real_sdk_disables_automatic_graph_span_but_restores_provider_child(
    monkeypatch, sdk_runs
):
    client, creates, updates = sdk_runs
    monkeypatch.setattr(
        tracing, "langsmith_tracing_enabled", lambda: True
    )
    secret_message = "full-user-message-must-not-leak"
    query = build_flight_query("北京", "上海", "2099-08-01")
    provider_result = ProviderResult(
        provider="sdk_provider",
        status=ProviderStatus.success,
        offers=[_offer()],
    )

    @traceable(name="automatic_graph_span")
    async def automatic_graph(state):
        result = await tracing.trace_provider_call(
            "sdk_provider", query, lambda: _async_value(provider_result)
        )
        return FrontendResponse(
            user_id="u1",
            session_id="s-sdk",
            deals=[{"price": result.offers[0].total_price}],
            analysis={},
            recommendation={},
            meta={},
        )

    with tracing_context(
        enabled=True, client=client, project_name="task-10-test"
    ):
        response = await tracing.trace_flight_search(
            "req-sdk",
            len(secret_message),
            lambda: automatic_graph({"request_message": secret_message}),
        )

    assert response.session_id == "s-sdk"
    assert [run["name"] for run in creates] == [
        "flight_search",
        "provider.sdk_provider",
        "stream_results",
    ]
    root = creates[0]
    provider = creates[1]
    stream = creates[2]
    assert provider["parent_run_id"] == root["id"]
    assert stream["parent_run_id"] == root["id"]
    assert provider["trace_id"] == stream["trace_id"] == root["trace_id"]
    assert {run["name"] for run in updates} == {
        "flight_search",
        "provider.sdk_provider",
        "stream_results",
    }
    sdk_payload = repr((creates, updates))
    assert "automatic_graph_span" not in sdk_payload
    assert secret_message not in sdk_payload
    assert "book.example.test" not in sdk_payload
    assert "raw-provider-payload" not in sdk_payload


@pytest.mark.asyncio
async def test_real_sdk_keeps_concurrent_search_roots_and_children_isolated(
    monkeypatch, sdk_runs
):
    client, creates, _updates = sdk_runs
    monkeypatch.setattr(tracing, "langsmith_tracing_enabled", lambda: True)
    query = build_flight_query("北京", "上海", "2099-08-01")
    arrived = 0
    release = asyncio.Event()

    async def rendezvous() -> None:
        nonlocal arrived
        arrived += 1
        if arrived == 2:
            release.set()
        await asyncio.wait_for(release.wait(), timeout=1)

    async def run_search(label: str) -> FrontendResponse:
        async def operation() -> FrontendResponse:
            await rendezvous()
            result = ProviderResult(
                provider=label,
                status=ProviderStatus.empty,
            )
            await tracing.trace_provider_call(
                label, query, lambda: _async_value(result)
            )
            return FrontendResponse(
                user_id="u1",
                session_id=f"session-{label}",
                deals=[],
                analysis={},
                recommendation={},
                meta={},
            )

        return await tracing.trace_flight_search(
            f"request-{label}", len(label), operation
        )

    with tracing_context(
        enabled=True, client=client, project_name="task-10-concurrency-test"
    ):
        left, right = await asyncio.gather(
            run_search("left"), run_search("right")
        )

    assert {left.session_id, right.session_id} == {
        "session-left",
        "session-right",
    }
    roots = {
        run["inputs"]["request_id"]: run
        for run in creates
        if run["name"] == "flight_search"
    }
    assert set(roots) == {"request-left", "request-right"}
    assert roots["request-left"]["id"] != roots["request-right"]["id"]
    assert roots["request-left"]["trace_id"] != roots["request-right"]["trace_id"]

    for label in ("left", "right"):
        root = roots[f"request-{label}"]
        provider = next(
            run for run in creates if run["name"] == f"provider.{label}"
        )
        stream = next(
            run
            for run in creates
            if run["name"] == "stream_results"
            and run["inputs"]["request_id"] == f"request-{label}"
        )
        assert provider["parent_run_id"] == root["id"]
        assert stream["parent_run_id"] == root["id"]
        assert provider["trace_id"] == stream["trace_id"] == root["trace_id"]


@pytest.mark.asyncio
async def test_real_sdk_isolates_concurrent_search_and_worker_trace_parents(
    monkeypatch, sdk_runs
):
    client, creates, _updates = sdk_runs
    monkeypatch.setattr(tracing, "langsmith_tracing_enabled", lambda: True)
    query = build_flight_query("北京", "上海", "2099-08-01")
    arrived = 0
    release = asyncio.Event()

    async def rendezvous() -> None:
        nonlocal arrived
        arrived += 1
        if arrived == 2:
            release.set()
        await asyncio.wait_for(release.wait(), timeout=1)

    async def search_operation() -> FrontendResponse:
        await rendezvous()
        result = ProviderResult(
            provider="search",
            status=ProviderStatus.empty,
        )
        await tracing.trace_provider_call(
            "search", query, lambda: _async_value(result)
        )
        return FrontendResponse(
            user_id="u1",
            session_id="search-session",
            deals=[],
            analysis={},
            recommendation={},
            meta={},
        )

    async def worker_operation() -> CtripRefreshSummary:
        await rendezvous()
        await tracing.trace_ctrip_demand(
            origin_code="CAN",
            destination_code="SHA",
            depart_date="2099-08-02",
            operation=lambda: _async_value([]),
        )
        return CtripRefreshSummary(processed=1, succeeded=1)

    with tracing_context(
        enabled=True, client=client, project_name="task-10-concurrency-test"
    ):
        search_result, worker_result = await asyncio.gather(
            tracing.trace_flight_search("request-search", 6, search_operation),
            tracing.trace_ctrip_refresh(worker_operation),
        )

    assert search_result.session_id == "search-session"
    assert worker_result.processed == 1
    search_root = next(run for run in creates if run["name"] == "flight_search")
    worker_root = next(
        run for run in creates if run["name"] == "ctrip_hourly_refresh"
    )
    provider = next(run for run in creates if run["name"] == "provider.search")
    stream = next(run for run in creates if run["name"] == "stream_results")
    demand = next(run for run in creates if run["name"] == "ctrip_demand")

    assert search_root["id"] != worker_root["id"]
    assert search_root["trace_id"] != worker_root["trace_id"]
    assert provider["parent_run_id"] == stream["parent_run_id"] == search_root["id"]
    assert provider["trace_id"] == stream["trace_id"] == search_root["trace_id"]
    assert demand["parent_run_id"] == worker_root["id"]
    assert demand["trace_id"] == worker_root["trace_id"]


@pytest.mark.asyncio
async def test_disabled_tracing_uses_no_sdk_runs_or_network(
    monkeypatch, sdk_runs
):
    client, creates, updates = sdk_runs
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGSMITH_API_KEY", "ls-test-key")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    get_settings.cache_clear()
    query = build_flight_query("北京", "上海", "2099-08-01")
    provider_result = ProviderResult(
        provider="disabled_provider",
        status=ProviderStatus.empty,
    )

    with tracing_context(enabled=True, client=client, project_name="task-10-test"):
        result = await tracing.trace_provider_call(
            "disabled_provider", query, lambda: _async_value(provider_result)
        )

    assert result is provider_result
    assert creates == []
    assert updates == []


@pytest.mark.asyncio
async def test_all_disabled_wrappers_bypass_custom_run_construction(monkeypatch):
    monkeypatch.setattr(
        tracing, "langsmith_tracing_enabled", lambda: False, raising=False
    )
    monkeypatch.setattr(
        tracing,
        "trace",
        lambda *args, **kwargs: pytest.fail("disabled tracing created a run"),
    )
    query = build_flight_query("北京", "上海", "2099-08-01")
    provider_result = ProviderResult(
        provider="disabled_provider",
        status=ProviderStatus.empty,
    )
    response = FrontendResponse(
        user_id="u1",
        deals=[],
        analysis={},
        recommendation={},
        meta={},
    )
    summary = CtripRefreshSummary()

    assert (
        await tracing.trace_provider_call(
            "disabled_provider", query, lambda: _async_value(provider_result)
        )
        is provider_result
    )
    assert tracing.trace_stage("rank_results", {}, lambda: []) == []
    assert (
        tracing.trace_validate_and_normalize_input(
            depart_date="2099-08-01", operation=lambda: "query"
        )
        == "query"
    )
    assert (
        await tracing.trace_flight_search(
            "req-disabled", 1, lambda: _async_value(response)
        )
        is response
    )
    assert await tracing.trace_ctrip_demand(
        origin_code="BJS",
        destination_code="SHA",
        depart_date="2099-08-01",
        operation=lambda: _async_value([]),
    ) == []
    assert (
        await tracing.trace_ctrip_refresh(lambda: _async_value(summary))
        is summary
    )


@pytest.mark.asyncio
async def test_provider_exception_is_reraised_after_safe_trace_end(trace_records):
    query = build_flight_query("北京", "上海", "2099-08-01")
    secret = "raw response api_key=must-not-leak"

    async def fail() -> ProviderResult:
        raise RuntimeError(secret)

    with pytest.raises(RuntimeError, match="must-not-leak"):
        await tracing.trace_provider_call("flyai", query, fail)

    assert trace_records[0].outputs == {
        "status": "error",
        "offer_count": 0,
        "latency_ms": pytest.approx(0, abs=1000),
        "cache_age_seconds": None,
    }
    assert trace_records[0].exit_exception is None
    assert trace_records[0].end_calls == 1
    assert secret not in repr(trace_records[0])


@pytest.mark.asyncio
async def test_provider_hard_timeout_is_recorded_as_timeout(trace_records):
    query = build_flight_query("北京", "上海", "2099-08-01")

    async def time_out() -> ProviderResult:
        return await asyncio.wait_for(asyncio.sleep(10), timeout=0.001)

    with pytest.raises(TimeoutError):
        await tracing.trace_provider_call("slow", query, time_out)

    assert trace_records[0].outputs["status"] == "timeout"
    assert trace_records[0].outputs["offer_count"] == 0
    assert trace_records[0].end_calls == 1
    assert trace_records[0].exit_exception is None


@pytest.mark.asyncio
async def test_provider_external_cancellation_is_recorded_as_cancelled(trace_records):
    query = build_flight_query("北京", "上海", "2099-08-01")
    started = asyncio.Event()

    async def hang() -> ProviderResult:
        started.set()
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    task = asyncio.create_task(tracing.trace_provider_call("slow", query, hang))
    await started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert trace_records[0].outputs["status"] == "cancelled"
    assert trace_records[0].end_calls == 1
    assert trace_records[0].exit_exception is None


def test_validate_and_normalize_span_records_no_raw_input_and_ends_once(
    trace_records,
):
    result = tracing.trace_validate_and_normalize_input(
        depart_date="2099-08-01",
        operation=lambda: "normalized",
    )

    assert result == "normalized"
    assert trace_records[0].name == "validate_and_normalize_input"
    assert trace_records[0].inputs == {
        "depart_date": "2099-08-01",
        "field_count": 3,
    }
    assert trace_records[0].outputs == {"status": "success"}
    assert trace_records[0].end_calls == 1


@pytest.mark.parametrize(
    "untrusted_depart_date",
    [
        "2099-02-30",
        "2099-8-01 DATE_SECRET_SENTINEL",
        "please fly tomorrow with DATE_SECRET_SENTINEL in this full sentence",
    ],
)
def test_invalid_depart_date_is_excluded_from_every_trace_repr(
    trace_records, untrusted_depart_date
):
    result = tracing.trace_validate_and_normalize_input(
        depart_date=untrusted_depart_date,
        operation=lambda: "rejected",
    )

    assert result == "rejected"
    assert trace_records[0].inputs == {
        "field_count": 3,
        "depart_date_present": True,
    }
    assert untrusted_depart_date not in repr(trace_records)
    assert "DATE_SECRET_SENTINEL" not in repr(trace_records)


def test_validate_and_normalize_exception_is_safely_reraised(trace_records):
    secret = "full message must not reach trace"

    def fail():
        raise ValueError(secret)

    with pytest.raises(ValueError, match="must not reach"):
        tracing.trace_validate_and_normalize_input(
            depart_date="not-a-date",
            operation=fail,
        )

    assert trace_records[0].outputs == {"status": "error"}
    assert trace_records[0].end_calls == 1
    assert trace_records[0].exit_exception is None
    assert secret not in repr(trace_records[0])


@pytest.mark.asyncio
async def test_cancelled_search_emits_no_complete_or_sensitive_error(trace_records):
    events: list[dict] = []

    async def cancel() -> FrontendResponse:
        raise asyncio.CancelledError("complete-user-message-must-not-leak")

    with bind_search_event_emitter(SearchEventEmitter("req-cancel", events.append)):
        with pytest.raises(asyncio.CancelledError):
            await tracing.trace_flight_search("req-cancel", 999, cancel)

    assert events == []
    assert [record.name for record in trace_records] == [
        "flight_search",
        "stream_results",
    ]
    assert trace_records[0].outputs == {"status": "cancelled", "result_count": 0}
    assert trace_records[1].outputs == {"status": "cancelled", "result_count": 0}
    assert "complete-user-message" not in repr(trace_records)
    assert all(record.end_calls == 1 for record in trace_records)


@pytest.mark.asyncio
async def test_failed_search_emits_one_sanitized_complete_from_stream_trace(
    trace_records,
):
    events: list[dict] = []
    secret = "full user message api_key=must-not-leak"

    async def fail() -> FrontendResponse:
        raise RuntimeError(secret)

    with bind_search_event_emitter(SearchEventEmitter("req-error", events.append)):
        with pytest.raises(RuntimeError, match="must-not-leak"):
            await tracing.trace_flight_search("req-error", 999, fail)

    assert [event["type"] for event in events] == ["complete"]
    assert events[0]["payload"] == {
        "error": "search_failed",
        "message": "搜索暂时不可用，请稍后重试",
    }
    assert trace_records[0].outputs == {"status": "error", "result_count": 0}
    assert trace_records[1].outputs == {"status": "error", "result_count": 0}
    assert secret not in repr(trace_records)
    assert secret not in repr(events)
    assert all(record.end_calls == 1 for record in trace_records)


@pytest.mark.asyncio
async def test_ctrip_refresh_has_independent_safe_root_trace(trace_records):
    summary = CtripRefreshSummary(processed=3, succeeded=2, failed=1)

    async def refresh_operation():
        await tracing.trace_ctrip_demand(
            origin_code="BJS",
            destination_code="SHA",
            depart_date="2099-08-01",
            operation=lambda: _async_value([{"booking_url": "https://secret"}]),
        )
        await tracing.trace_ctrip_demand(
            origin_code="CAN",
            destination_code="SHA",
            depart_date="2099-08-02",
            operation=lambda: _async_value([]),
        )
        return summary

    result = await tracing.trace_ctrip_refresh(refresh_operation)

    assert result == summary
    assert [(record.name, record.parent) for record in trace_records] == [
        ("ctrip_hourly_refresh", None),
        ("ctrip_demand", "ctrip_hourly_refresh"),
        ("ctrip_demand", "ctrip_hourly_refresh"),
    ]
    assert trace_records[0].inputs == {"schedule": "hourly"}
    assert trace_records[0].outputs == {
        "processed": 3,
        "succeeded": 2,
        "failed": 1,
        "skipped_overlap": False,
    }
    assert trace_records[1].inputs == {
        "origin_code": "BJS",
        "destination_code": "SHA",
        "depart_date": "2099-08-01",
    }
    assert trace_records[1].outputs["status"] == "success"
    assert trace_records[1].outputs["row_count"] == 1
    assert trace_records[2].outputs["status"] == "empty"
    assert trace_records[2].outputs["row_count"] == 0
    assert "booking_url" not in repr(trace_records)
    assert all(record.end_calls == 1 for record in trace_records)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (RuntimeError("raw worker response must not leak"), "error"),
        (asyncio.CancelledError("worker cancellation payload"), "cancelled"),
    ],
)
async def test_ctrip_refresh_exception_and_cancel_are_safely_reraised(
    trace_records, error, expected_status
):
    async def fail():
        raise error

    with pytest.raises(type(error)):
        await tracing.trace_ctrip_refresh(fail)

    assert trace_records[0].outputs == {
        "status": expected_status,
        "processed": 0,
        "succeeded": 0,
        "failed": 0,
        "skipped_overlap": False,
    }
    assert trace_records[0].end_calls == 1
    assert trace_records[0].exit_exception is None
    assert str(error) not in repr(trace_records[0])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "expected_status"),
    [
        (RuntimeError("raw demand rows must not leak"), "error"),
        (asyncio.CancelledError("demand cancellation payload"), "cancelled"),
    ],
)
async def test_ctrip_demand_exception_and_cancel_are_safely_reraised(
    trace_records, error, expected_status
):
    async def fail():
        raise error

    with pytest.raises(type(error)):
        await tracing.trace_ctrip_demand(
            origin_code="BJS",
            destination_code="SHA",
            depart_date="2099-08-01",
            operation=fail,
        )

    assert trace_records[0].outputs["status"] == expected_status
    assert trace_records[0].outputs["row_count"] == 0
    assert trace_records[0].end_calls == 1
    assert trace_records[0].exit_exception is None
    assert str(error) not in repr(trace_records[0])


async def _async_value(value):
    return value
