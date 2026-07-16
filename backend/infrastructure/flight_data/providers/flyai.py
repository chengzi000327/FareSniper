from __future__ import annotations

import asyncio
import json
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

from backend.application.contracts.flight_provider import (
    FlightOffer,
    FlightQuery,
    PriceStatus,
    ProviderResult,
    ProviderStatus,
)


_TRANSIENT_ERROR_MARKERS = (
    "timeout",
    "timed out",
    "connection reset",
    "temporary network failure",
    "temporarily unavailable",
    "network is unreachable",
    "econnreset",
    "econnrefused",
    "etimedout",
)


@dataclass
class _RunResult:
    stdout: bytes = b""
    stderr: bytes = b""
    returncode: int | None = None
    timed_out: bool = False
    launch_error: OSError | None = None


def _is_https_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def _parse_price(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    text = str(value).strip()
    if not text:
        return None
    cleaned = re.sub(r"[^0-9.+-]", "", text)
    if not cleaned:
        return None
    try:
        price = Decimal(cleaned)
    except (InvalidOperation, ValueError):
        return None
    if not price.is_finite() or price < 0:
        return None
    return int(price)


def _time_part(value: object) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip().replace("T", " ")
    if " " not in text:
        return text[:5]
    return text.split(" ", 1)[1][:5]


def _minutes(value: object) -> int | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)
    if not isinstance(value, str):
        return None
    match = re.search(r"(\d+)", value)
    return int(match.group(1)) if match else None


def _segments_for(item: dict) -> list[dict]:
    segments: list[dict] = []
    journeys = item.get("journeys") or []
    if not isinstance(journeys, list):
        return segments
    for journey in journeys:
        if not isinstance(journey, dict):
            continue
        journey_segments = journey.get("segments") or []
        if isinstance(journey_segments, list):
            segments.extend(segment for segment in journey_segments if isinstance(segment, dict))
    return segments


def parse_flyai_payload(payload: dict, query: FlightQuery) -> list[FlightOffer]:
    data = payload.get("data") or {}
    items = data.get("itemList") if isinstance(data, dict) else []
    if not isinstance(items, list):
        return []

    offers: list[FlightOffer] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        segments = _segments_for(item)
        if not segments:
            continue

        price = _parse_price(item.get("adultPrice"))
        jump_url = item.get("jumpUrl")
        booking_url = jump_url if _is_https_url(jump_url) else None
        if price is None and booking_url is None:
            continue

        first_segment = segments[0]
        last_segment = segments[-1]
        flight_numbers = [
            str(segment.get("marketingTransportNo", "")).strip()
            for segment in segments
            if segment.get("marketingTransportNo")
        ]
        airlines = [
            str(segment.get("marketingTransportName", "")).strip()
            for segment in segments
            if segment.get("marketingTransportName")
        ]
        price_status = (
            PriceStatus.priced if price is not None else PriceStatus.view_live_price
        )
        total_duration = item.get("totalDuration")
        if total_duration is None:
            total_duration = next(
                (
                    journey.get("totalDuration")
                    for journey in item.get("journeys", [])
                    if isinstance(journey, dict) and journey.get("totalDuration") is not None
                ),
                None,
            )

        offers.append(
            FlightOffer(
                data_provider="flyai",
                seller_name="飞猪",
                flight_no="/".join(flight_numbers),
                airline="/".join(airlines),
                origin_city=query.origin_city,
                origin_code=query.origin_code,
                destination_city=query.destination_city,
                destination_code=query.destination_code,
                depart_date=query.depart_date,
                depart_time=_time_part(first_segment.get("depDateTime")),
                arrive_time=_time_part(last_segment.get("arrDateTime")),
                duration_minutes=_minutes(total_duration),
                stops=max(0, len(segments) - 1),
                cabin=first_segment.get("seatClassName"),
                total_price=price,
                tax=None,
                baggage_fee=None,
                has_baggage=None,
                price_status=price_status,
                booking_url=booking_url,
            )
        )
    return offers


class FlyAIProvider:
    name = "flyai"

    def __init__(self, *, api_key, cli_path="flyai", timeout_seconds=10.0):
        self._api_key = api_key
        self._cli_path = cli_path
        self._timeout_seconds = timeout_seconds

    def supports(self, query: FlightQuery) -> bool:
        return True

    async def _run_once(self, query: FlightQuery) -> _RunResult:
        env = os.environ.copy()
        env["FLYAI_API_KEY"] = self._api_key
        try:
            process = await asyncio.create_subprocess_exec(
                self._cli_path,
                "search-flight",
                "--origin",
                query.origin_city,
                "--destination",
                query.destination_city,
                "--dep-date",
                query.depart_date,
                "--sort-type",
                "3",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
            )
        except OSError as exc:
            return _RunResult(launch_error=exc)

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self._timeout_seconds
            )
        except asyncio.TimeoutError:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.wait()
            return _RunResult(timed_out=True)
        return _RunResult(
            stdout=stdout,
            stderr=stderr,
            returncode=process.returncode,
        )

    @staticmethod
    def _is_transient(stderr: bytes) -> bool:
        text = stderr.decode("utf-8", errors="replace").lower()
        return any(marker in text for marker in _TRANSIENT_ERROR_MARKERS)

    @staticmethod
    def _error_result(error_code: str) -> ProviderResult:
        return ProviderResult(
            provider="flyai",
            status=ProviderStatus.error,
            error_code=error_code,
        )

    async def search(self, query: FlightQuery) -> ProviderResult:
        if not self._api_key:
            return ProviderResult(provider=self.name, status=ProviderStatus.disabled)

        run = await self._run_once(query)
        if run.timed_out:
            return ProviderResult(provider=self.name, status=ProviderStatus.timeout)
        if run.launch_error is not None:
            return self._error_result("cli_failed")

        if run.returncode != 0 and self._is_transient(run.stderr):
            run = await self._run_once(query)
            if run.timed_out:
                return ProviderResult(provider=self.name, status=ProviderStatus.timeout)
            if run.launch_error is not None:
                return self._error_result("cli_failed")

        if run.returncode != 0:
            text = run.stderr.decode("utf-8", errors="replace").lower()
            auth = any(token in text for token in ("401", "unauthorized", "api key"))
            return self._error_result("authentication" if auth else "cli_failed")

        try:
            payload = json.loads(run.stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._error_result("invalid_json")

        if not isinstance(payload, Mapping):
            return self._error_result("upstream_response")

        if payload.get("status") not in (None, 0, "0"):
            return self._error_result("upstream_response")

        offers = parse_flyai_payload(payload, query)
        return ProviderResult(
            provider=self.name,
            status=ProviderStatus.success if offers else ProviderStatus.empty,
            offers=offers,
        )
