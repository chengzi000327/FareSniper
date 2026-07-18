from __future__ import annotations

from contextlib import nullcontext
from types import SimpleNamespace

import pytest

from backend.infrastructure.observability import collector_tracing


class _TraceRecord:
    def __init__(self, *, name: str, run_type: str, inputs: dict):
        self.name = name
        self.run_type = run_type
        self.inputs = inputs
        self.outputs = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def end(self, *, outputs: dict):
        self.outputs = outputs


@pytest.fixture
def trace_records(monkeypatch):
    records: list[_TraceRecord] = []

    def fake_trace(*, name: str, run_type: str, inputs: dict):
        record = _TraceRecord(name=name, run_type=run_type, inputs=inputs)
        records.append(record)
        return record

    monkeypatch.setattr(
        collector_tracing, "langsmith_tracing_enabled", lambda: True
    )
    monkeypatch.setattr(collector_tracing, "trace", fake_trace)
    monkeypatch.setattr(
        collector_tracing,
        "tracing_context",
        lambda **_kwargs: nullcontext(),
    )
    return records


@pytest.mark.asyncio
async def test_claim_trace_contains_only_anonymous_summary(trace_records):
    raw_job_id = "raw-job-id-must-not-leak"

    async def operation():
        return SimpleNamespace(job_id=raw_job_id)

    result = await collector_tracing.trace_collector_claim(operation)

    assert result.job_id == raw_job_id
    assert len(trace_records) == 1
    record = trace_records[0]
    assert record.name == "ctrip_collector_claim"
    assert record.run_type == "tool"
    assert record.inputs == {}
    assert set(record.outputs) == {
        "anonymous_job_id",
        "result_count",
        "status",
        "duration_ms",
    }
    assert record.outputs["anonymous_job_id"] != raw_job_id
    assert record.outputs["result_count"] == 1
    assert record.outputs["status"] == "success"
    assert isinstance(record.outputs["duration_ms"], int)
    assert raw_job_id not in repr(record.inputs) + repr(record.outputs)


@pytest.mark.asyncio
async def test_empty_claim_trace_has_no_job_identifier(trace_records):
    async def operation():
        return None

    assert await collector_tracing.trace_collector_claim(operation) is None

    assert trace_records[0].outputs["anonymous_job_id"] is None
    assert trace_records[0].outputs["result_count"] == 0
    assert trace_records[0].outputs["status"] == "empty"


@pytest.mark.asyncio
async def test_collector_trace_starts_with_no_inherited_parent(
    monkeypatch, trace_records
):
    contexts = []

    def capture_context(**kwargs):
        contexts.append(kwargs)
        return nullcontext()

    monkeypatch.setattr(
        collector_tracing, "tracing_context", capture_context
    )

    async def operation():
        return None

    await collector_tracing.trace_collector_claim(operation)

    assert contexts == [{"enabled": True, "parent": False}]


@pytest.mark.asyncio
async def test_ingest_trace_hashes_job_and_never_records_offer_data(trace_records):
    raw_job_id = "raw-ingest-job-id"
    raw_offer_secret = "cookie-raw-offer-browser-state-secret"

    async def operation():
        _ = raw_offer_secret
        return True

    assert await collector_tracing.trace_collector_ingest(
        raw_job_id, 3, operation
    ) is True

    record = trace_records[0]
    assert record.name == "ctrip_collector_ingest"
    assert record.run_type == "tool"
    assert record.inputs == {}
    assert set(record.outputs) == {
        "anonymous_job_id",
        "result_count",
        "status",
        "duration_ms",
    }
    assert record.outputs["anonymous_job_id"] != raw_job_id
    assert record.outputs["result_count"] == 3
    assert record.outputs["status"] == "success"
    trace_payload = repr(record.inputs) + repr(record.outputs)
    assert raw_job_id not in trace_payload
    assert raw_offer_secret not in trace_payload


@pytest.mark.asyncio
async def test_collector_trace_reraises_with_safe_error_summary(trace_records):
    secret = "token-cookie-browser-state-secret"

    async def operation():
        raise RuntimeError(secret)

    with pytest.raises(RuntimeError, match=secret):
        await collector_tracing.trace_collector_ingest(
            "raw-job-id", 4, operation
        )

    outputs = trace_records[0].outputs
    assert outputs["status"] == "error"
    assert outputs["result_count"] == 0
    assert secret not in repr(trace_records[0].inputs) + repr(outputs)


@pytest.mark.asyncio
async def test_disabled_collector_tracing_runs_operation_without_span(monkeypatch):
    monkeypatch.setattr(
        collector_tracing, "langsmith_tracing_enabled", lambda: False
    )

    async def operation():
        return "ok"

    assert await collector_tracing.trace_collector_ingest(
        "raw-job-id", 1, operation
    ) == "ok"
