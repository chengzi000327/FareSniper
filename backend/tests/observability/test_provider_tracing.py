from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import pytest

import backend.infrastructure.observability.provider_tracing as tracing
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


class _FakeRun:
    def __init__(self, record: _TraceRecord) -> None:
        self._record = record

    def end(self, *, outputs: dict[str, Any]) -> None:
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
    return records


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


@pytest.mark.asyncio
async def test_ctrip_refresh_has_independent_safe_root_trace(trace_records):
    summary = CtripRefreshSummary(processed=3, succeeded=2, failed=1)

    result = await tracing.trace_ctrip_refresh(lambda: _async_value(summary))

    assert result == summary
    assert [(record.name, record.parent) for record in trace_records] == [
        ("ctrip_hourly_refresh", None)
    ]
    assert trace_records[0].inputs == {"schedule": "hourly"}
    assert trace_records[0].outputs == {
        "processed": 3,
        "succeeded": 2,
        "failed": 1,
        "skipped_overlap": False,
    }


async def _async_value(value):
    return value
