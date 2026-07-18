from __future__ import annotations

import asyncio
import hashlib
import time
from collections.abc import Awaitable, Callable
from typing import TypeVar

from langsmith import trace, tracing_context

from backend.config import langsmith_tracing_enabled


T = TypeVar("T")


def _anonymous_job_id(job_id: str | None) -> str | None:
    if job_id is None:
        return None
    return hashlib.sha256(
        f"faresniper-collector-job:{job_id}".encode("utf-8")
    ).hexdigest()[:16]


def _exception_status(error: BaseException) -> str:
    if isinstance(error, TimeoutError):
        return "timeout"
    if isinstance(error, asyncio.CancelledError):
        return "cancelled"
    return "error"


def _summary(
    *,
    job_id: str | None,
    result_count: int,
    status: str,
    started_at: float,
) -> dict[str, str | int | None]:
    return {
        "anonymous_job_id": _anonymous_job_id(job_id),
        "result_count": result_count,
        "status": status,
        "duration_ms": int((time.monotonic() - started_at) * 1000),
    }


def _reraise(error: BaseException) -> None:
    raise error.with_traceback(error.__traceback__)


async def trace_collector_claim(
    operation: Callable[[], Awaitable[T]],
) -> T:
    if not langsmith_tracing_enabled():
        with tracing_context(enabled=False):
            return await operation()

    started_at = time.monotonic()
    result: T | None = None
    error: BaseException | None = None
    with tracing_context(enabled=True, parent=False):
        with trace(
            name="ctrip_collector_claim",
            run_type="tool",
            inputs={},
        ) as run:
            try:
                result = await operation()
            except BaseException as exc:
                error = exc
                run.end(
                    outputs=_summary(
                        job_id=None,
                        result_count=0,
                        status=_exception_status(exc),
                        started_at=started_at,
                    )
                )
            else:
                job_id = getattr(result, "job_id", None)
                run.end(
                    outputs=_summary(
                        job_id=job_id if isinstance(job_id, str) else None,
                        result_count=1 if result is not None else 0,
                        status="success" if result is not None else "empty",
                        started_at=started_at,
                    )
                )

    if error is not None:
        _reraise(error)
    return result  # type: ignore[return-value]


async def trace_collector_ingest(
    job_id: str,
    result_count: int,
    operation: Callable[[], Awaitable[T]],
) -> T:
    if not langsmith_tracing_enabled():
        with tracing_context(enabled=False):
            return await operation()

    started_at = time.monotonic()
    result: T | None = None
    error: BaseException | None = None
    with tracing_context(enabled=True, parent=False):
        with trace(
            name="ctrip_collector_ingest",
            run_type="tool",
            inputs={},
        ) as run:
            try:
                result = await operation()
            except BaseException as exc:
                error = exc
                run.end(
                    outputs=_summary(
                        job_id=job_id,
                        result_count=0,
                        status=_exception_status(exc),
                        started_at=started_at,
                    )
                )
            else:
                run.end(
                    outputs=_summary(
                        job_id=job_id,
                        result_count=result_count,
                        status="success",
                        started_at=started_at,
                    )
                )

    if error is not None:
        _reraise(error)
    return result  # type: ignore[return-value]
