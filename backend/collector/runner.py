from __future__ import annotations

import asyncio
import hashlib
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol

from langsmith import trace, tracing_context

from backend.application.contracts.collector import CollectorErrorCode
from backend.application.contracts.flight_provider import FlightOffer
from backend.application.services.flight_query import (
    FlightQueryValidationError,
    build_flight_query,
)
from backend.collector.browser import CaptureResult, build_search_url
from backend.config import langsmith_tracing_enabled
from backend.infrastructure.flight_data.ctrip_parser import (
    CtripBatchSearchParseError,
    parse_batch_search,
)


class CollectorApi(Protocol):
    async def heartbeat(self, status: str) -> None: ...

    async def claim(self) -> object | None: ...

    async def complete(
        self, job_id: str, offers: list[FlightOffer]
    ) -> None: ...

    async def fail(
        self,
        job_id: str,
        error_code: CollectorErrorCode,
        retry_at: datetime,
    ) -> None: ...


class CollectorBrowser(Protocol):
    async def capture(self, job: object) -> CaptureResult: ...

    async def reset_session(self) -> None: ...


@dataclass(frozen=True)
class RunResult:
    status: str
    result_count: int = 0


class CollectorRunner:
    def __init__(
        self,
        api: CollectorApi,
        browser: CollectorBrowser,
        *,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.api = api
        self.browser = browser
        self._now = now or (lambda: datetime.now(timezone.utc))

    async def run_once(self) -> RunResult:
        await self.api.heartbeat("idle")
        job = await self.api.claim()
        if job is None:
            return RunResult(status="idle")
        return await self._trace_claimed_job(job)

    async def run_daemon(
        self,
        *,
        stop_requested: Callable[[], bool],
        interval_seconds: float = 60.0,
        wait_for_stop: Callable[[float], Awaitable[bool]] | None = None,
    ) -> None:
        if interval_seconds <= 0:
            raise ValueError("collector interval must be positive")
        while not stop_requested():
            await self.run_once()
            if stop_requested():
                break
            if wait_for_stop is None:
                await asyncio.sleep(interval_seconds)
            elif await wait_for_stop(interval_seconds):
                break

    async def _trace_claimed_job(self, job: object) -> RunResult:
        if not langsmith_tracing_enabled():
            with tracing_context(enabled=False):
                return await self._run_claimed_job(job)

        started_at = time.monotonic()
        anonymous_job_id = hashlib.sha256(
            f"faresniper-local-collector:{getattr(job, 'job_id', '')}".encode()
        ).hexdigest()[:16]
        result: RunResult | None = None
        error: BaseException | None = None
        with tracing_context(enabled=True, parent=False):
            with trace(
                name="ctrip_local_collect",
                run_type="tool",
                inputs={},
            ) as run:
                try:
                    result = await self._run_claimed_job(job)
                except BaseException as exc:
                    error = exc
                    run.end(
                        outputs={
                            "anonymous_job_id": anonymous_job_id,
                            "status": "error",
                            "result_count": 0,
                            "duration_ms": int(
                                (time.monotonic() - started_at) * 1000
                            ),
                        }
                    )
                else:
                    run.end(
                        outputs={
                            "anonymous_job_id": anonymous_job_id,
                            "status": result.status,
                            "result_count": result.result_count,
                            "duration_ms": int(
                                (time.monotonic() - started_at) * 1000
                            ),
                        }
                    )
        if error is not None:
            raise error.with_traceback(error.__traceback__)
        return result  # type: ignore[return-value]

    async def _run_claimed_job(self, job: object) -> RunResult:
        job_id = str(getattr(job, "job_id", ""))
        try:
            capture = await self.browser.capture(job)
        except asyncio.CancelledError:
            raise
        except Exception:
            return await self._fail_once(
                job_id,
                CollectorErrorCode.dependency_error,
            )
        if capture.error_code is not None:
            return await self._fail_once(job_id, capture.error_code)

        try:
            origin_airport_scope = getattr(
                job, "origin_airport_code", None
            )
            destination_airport_scope = getattr(
                job, "destination_airport_code", None
            )
            query = build_flight_query(
                str(origin_airport_scope or getattr(job, "origin_code", "")),
                str(
                    destination_airport_scope
                    or getattr(job, "destination_code", "")
                ),
                str(getattr(job, "depart_date", "")),
            )
            query = query.model_copy(
                update={
                    "origin_code": str(
                        getattr(job, "origin_code", query.origin_code)
                    ),
                    "origin_airport_scope": origin_airport_scope,
                    "destination_code": str(
                        getattr(
                            job,
                            "destination_code",
                            query.destination_code,
                        )
                    ),
                    "destination_airport_scope": (
                        destination_airport_scope
                    ),
                }
            )
            offers: list[FlightOffer] = []
            for payload in capture.payloads:
                offers.extend(parse_batch_search(payload, query))
            if not self._offers_match_job(offers, job):
                raise CtripBatchSearchParseError(
                    "batchSearch result does not match claimed job"
                )
        except (CtripBatchSearchParseError, FlightQueryValidationError):
            return await self._reset_and_fail(
                job_id,
                CollectorErrorCode.parse_error,
            )

        if not offers:
            return await self._fail_once(job_id, CollectorErrorCode.empty)

        booking_url = build_search_url(job)
        normalized = [
            offer.model_copy(
                update={
                    "booking_url": booking_url,
                    "raw_reference": None,
                }
            )
            for offer in offers
        ]
        await self.api.complete(job_id, normalized)
        return RunResult(status="success", result_count=len(normalized))

    @staticmethod
    def _offers_match_job(
        offers: list[FlightOffer],
        job: object,
    ) -> bool:
        expected_origin = str(getattr(job, "origin_code", "")).upper()
        expected_destination = str(
            getattr(job, "destination_code", "")
        ).upper()
        expected_origin_airport = getattr(
            job, "origin_airport_code", None
        )
        expected_destination_airport = getattr(
            job, "destination_airport_code", None
        )
        expected_date = str(getattr(job, "depart_date", ""))
        return all(
            offer.origin_code.upper() == expected_origin
            and offer.destination_code.upper() == expected_destination
            and (
                expected_origin_airport is None
                or offer.origin_airport_code == expected_origin_airport
            )
            and (
                expected_destination_airport is None
                or offer.destination_airport_code
                == expected_destination_airport
            )
            and offer.depart_date == expected_date
            for offer in offers
        )

    async def _fail_once(
        self,
        job_id: str,
        error_code: CollectorErrorCode,
    ) -> RunResult:
        retry_at = self._now() + timedelta(minutes=5)
        await self.api.fail(job_id, error_code, retry_at)
        return RunResult(status=error_code.value)

    async def _reset_and_fail(
        self,
        job_id: str,
        error_code: CollectorErrorCode,
    ) -> RunResult:
        try:
            await self.browser.reset_session()
        except Exception:
            pass
        return await self._fail_once(job_id, error_code)
