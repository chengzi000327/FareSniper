from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Protocol, TypeVar

from langsmith import trace

from backend.application.contracts.decision import FrontendResponse
from backend.application.contracts.flight_provider import FlightQuery, ProviderResult
from backend.application.services.search_events import emit_search_event


T = TypeVar("T")


class _CtripRefreshSummary(Protocol):
    processed: int
    succeeded: int
    failed: int
    skipped_overlap: bool


_SAFE_STAGE_INPUT_KEYS = {
    "provider",
    "origin_code",
    "destination_code",
    "depart_date",
    "request_id",
    "message_length",
    "schedule",
    "count",
    "provider_count",
    "result_count",
}


def safe_provider_inputs(
    *,
    provider: str,
    origin_code: str,
    destination_code: str,
    depart_date: str,
) -> dict[str, str]:
    return {
        "provider": provider,
        "origin_code": origin_code,
        "destination_code": destination_code,
        "depart_date": depart_date,
    }


def safe_provider_outputs(
    *,
    status: str,
    offer_count: int,
    latency_ms: int,
    cache_age_seconds: int | None,
) -> dict[str, str | int | None]:
    return {
        "status": status,
        "offer_count": offer_count,
        "latency_ms": latency_ms,
        "cache_age_seconds": cache_age_seconds,
    }


def _safe_stage_inputs(inputs: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in inputs.items()
        if key in _SAFE_STAGE_INPUT_KEYS
        and isinstance(value, (str, int, float, bool, type(None)))
    }


def _exception_status(error: BaseException) -> str:
    if isinstance(error, asyncio.CancelledError):
        return "cancelled"
    return "error"


def _reraise(error: BaseException) -> None:
    raise error.with_traceback(error.__traceback__)


async def trace_provider_call(
    provider: str,
    query: FlightQuery,
    operation: Callable[[], Awaitable[ProviderResult]],
) -> ProviderResult:
    started_at = time.monotonic()
    result: ProviderResult | None = None
    error: BaseException | None = None

    with trace(
        name=f"provider.{provider}",
        run_type="tool",
        inputs=safe_provider_inputs(
            provider=provider,
            origin_code=query.origin_code,
            destination_code=query.destination_code,
            depart_date=query.depart_date,
        ),
    ) as run:
        try:
            result = await operation()
        except BaseException as exc:
            error = exc
            run.end(
                outputs=safe_provider_outputs(
                    status=_exception_status(exc),
                    offer_count=0,
                    latency_ms=int((time.monotonic() - started_at) * 1000),
                    cache_age_seconds=None,
                )
            )
        else:
            run.end(
                outputs=safe_provider_outputs(
                    status=result.status.value,
                    offer_count=len(result.offers),
                    latency_ms=result.latency_ms,
                    cache_age_seconds=result.cache_age_seconds,
                )
            )

    if error is not None:
        _reraise(error)
    assert result is not None
    return result


def trace_stage(
    name: str,
    inputs: Mapping[str, Any],
    operation: Callable[[], T],
) -> T:
    output: T | None = None
    error: BaseException | None = None

    with trace(
        name=name,
        run_type="chain",
        inputs=_safe_stage_inputs(inputs),
    ) as run:
        try:
            output = operation()
        except BaseException as exc:
            error = exc
            run.end(outputs={"status": _exception_status(exc), "result_count": 0})
        else:
            run.end(outputs={"result_count": len(output)})  # type: ignore[arg-type]

    if error is not None:
        _reraise(error)
    return output  # type: ignore[return-value]


async def trace_flight_search(
    request_id: str,
    message_length: int,
    operation: Callable[[], Awaitable[FrontendResponse]],
) -> FrontendResponse:
    response: FrontendResponse | None = None
    error: BaseException | None = None

    with trace(
        name="flight_search",
        run_type="chain",
        inputs={"request_id": request_id, "message_length": message_length},
    ) as run:
        try:
            response = await operation()
        except BaseException as exc:
            error = exc
            status = _exception_status(exc)
            with trace(
                name="stream_results",
                run_type="chain",
                inputs={"request_id": request_id},
            ) as stream_run:
                if not isinstance(exc, asyncio.CancelledError):
                    emit_search_event(
                        "complete",
                        {
                            "error": "search_failed",
                            "message": "搜索暂时不可用，请稍后重试",
                        },
                    )
                stream_run.end(outputs={"status": status, "result_count": 0})
            run.end(outputs={"status": status, "result_count": 0})
        else:
            with trace(
                name="stream_results",
                run_type="chain",
                inputs={"request_id": request_id},
            ) as stream_run:
                emit_search_event(
                    "complete",
                    {"response": response.model_dump(mode="json")},
                )
                stream_run.end(outputs={"event_type": "complete"})
            run.end(
                outputs={
                    "deal_count": len(response.deals),
                    "has_recommendation": bool(response.recommendation),
                }
            )

    if error is not None:
        _reraise(error)
    assert response is not None
    return response


async def trace_ctrip_refresh(
    operation: Callable[[], Awaitable[_CtripRefreshSummary]],
) -> _CtripRefreshSummary:
    summary: _CtripRefreshSummary | None = None
    error: BaseException | None = None

    with trace(
        name="ctrip_hourly_refresh",
        run_type="chain",
        inputs={"schedule": "hourly"},
    ) as run:
        try:
            summary = await operation()
        except BaseException as exc:
            error = exc
            run.end(
                outputs={
                    "status": _exception_status(exc),
                    "processed": 0,
                    "succeeded": 0,
                    "failed": 0,
                    "skipped_overlap": False,
                }
            )
        else:
            run.end(
                outputs={
                    "processed": summary.processed,
                    "succeeded": summary.succeeded,
                    "failed": summary.failed,
                    "skipped_overlap": summary.skipped_overlap,
                }
            )

    if error is not None:
        _reraise(error)
    assert summary is not None
    return summary
