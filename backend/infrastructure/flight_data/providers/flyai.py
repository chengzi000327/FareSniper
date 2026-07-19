from __future__ import annotations

import asyncio
import json
import os
import re
import signal
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
    run_error: bool = False
    process: asyncio.subprocess.Process | None = None


_CHILD_ENV_ALLOWLIST = (
    "PATH",
    "HOME",
    "TMPDIR",
    "LANG",
    "LC_ALL",
    "SSL_CERT_FILE",
    "SSL_CERT_DIR",
    "NODE_EXTRA_CA_CERTS",
)


def _child_environment(api_key: str) -> dict[str, str]:
    env = {
        key: os.environ[key]
        for key in _CHILD_ENV_ALLOWLIST
        if key in os.environ
    }
    env["FLYAI_API_KEY"] = api_key
    return env


async def _terminate_process_group(process: asyncio.subprocess.Process) -> None:
    terminated = False
    pid = getattr(process, "pid", None)
    if os.name == "posix" and isinstance(pid, int):
        try:
            os.killpg(pid, signal.SIGKILL)
            terminated = True
        except ProcessLookupError:
            terminated = True
    if not terminated and process.returncode is None:
        try:
            process.kill()
        except ProcessLookupError:
            pass
    try:
        await process.wait()
    except ProcessLookupError:
        pass


async def _cleanup_error_run(run: _RunResult) -> None:
    if run.process is not None:
        await _terminate_process_group(run.process)


def _error_result(error_code: str) -> ProviderResult:
    return ProviderResult(
        provider="flyai",
        status=ProviderStatus.error,
        error_code=error_code,
    )


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


def _airport_code(value: object, fallback: object) -> str | None:
    for candidate in (value, fallback):
        if not isinstance(candidate, str):
            continue
        code = candidate.strip()
        if len(code) == 3 and code.isascii() and code.isalpha():
            return code.upper()
    return None


def _provider_location(query: FlightQuery, side: str) -> str:
    location = getattr(query, side, None)
    if location is not None:
        return location.airport_iata or location.provider_code("flyai")
    return getattr(query, f"{side}_city")


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

        price = _parse_price(item.get("ticketPrice"))
        if price is None:
            price = _parse_price(item.get("adultPrice"))
        jump_url = item.get("jumpUrl")
        booking_url = jump_url if _is_https_url(jump_url) else None
        if price is None and booking_url is None:
            continue

        first_segment = segments[0]
        last_segment = segments[-1]
        origin_scope = _airport_code(query.origin_airport_scope, None)
        destination_scope = _airport_code(
            query.destination_airport_scope, None
        )
        origin_airport_code = _airport_code(
            first_segment.get("depStationCode"), origin_scope
        )
        destination_airport_code = _airport_code(
            last_segment.get("arrStationCode"), destination_scope
        )
        if (
            origin_scope is not None
            and origin_airport_code != origin_scope
        ) or (
            destination_scope is not None
            and destination_airport_code != destination_scope
        ):
            continue
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
                origin_airport_code=origin_airport_code,
                destination_city=query.destination_city,
                destination_code=query.destination_code,
                destination_airport_code=destination_airport_code,
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
        try:
            process = await asyncio.create_subprocess_exec(
                self._cli_path,
                "search-flight",
                "--origin",
                _provider_location(query, "origin"),
                "--destination",
                _provider_location(query, "destination"),
                "--dep-date",
                query.depart_date,
                "--sort-type",
                "3",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=_child_environment(self._api_key),
                start_new_session=os.name == "posix",
            )
        except OSError as exc:
            return _RunResult(launch_error=exc)

        try:
            stdout, stderr = await asyncio.wait_for(
                process.communicate(), timeout=self._timeout_seconds
            )
        except asyncio.TimeoutError:
            await _terminate_process_group(process)
            return _RunResult(timed_out=True)
        except asyncio.CancelledError:
            await _terminate_process_group(process)
            raise
        except Exception:
            await _terminate_process_group(process)
            return _RunResult(run_error=True)
        return _RunResult(
            stdout=stdout,
            stderr=stderr,
            returncode=process.returncode,
            process=process,
        )

    @staticmethod
    def _is_transient(stderr: bytes) -> bool:
        text = stderr.decode("utf-8", errors="replace").lower()
        return any(marker in text for marker in _TRANSIENT_ERROR_MARKERS)

    async def search(self, query: FlightQuery) -> ProviderResult:
        if not self._api_key:
            return ProviderResult(provider=self.name, status=ProviderStatus.disabled)

        run = await self._run_once(query)
        if run.timed_out:
            return ProviderResult(provider=self.name, status=ProviderStatus.timeout)
        if run.launch_error is not None or run.run_error:
            return _error_result("cli_failed")

        if run.returncode != 0 and self._is_transient(run.stderr):
            await _cleanup_error_run(run)
            run = await self._run_once(query)
            if run.timed_out:
                return ProviderResult(provider=self.name, status=ProviderStatus.timeout)
            if run.launch_error is not None or run.run_error:
                return _error_result("cli_failed")

        if run.returncode != 0:
            await _cleanup_error_run(run)
            text = run.stderr.decode("utf-8", errors="replace").lower()
            auth = any(token in text for token in ("401", "unauthorized", "api key"))
            return _error_result("authentication" if auth else "cli_failed")

        try:
            payload = json.loads(run.stdout.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            await _cleanup_error_run(run)
            return _error_result("invalid_json")

        if not isinstance(payload, Mapping):
            await _cleanup_error_run(run)
            return _error_result("upstream_response")

        if payload.get("status") not in (None, 0, "0"):
            await _cleanup_error_run(run)
            return _error_result("upstream_response")

        try:
            offers = parse_flyai_payload(payload, query)
        except Exception:
            await _cleanup_error_run(run)
            return _error_result("upstream_response")
        return ProviderResult(
            provider=self.name,
            status=ProviderStatus.success if offers else ProviderStatus.empty,
            offers=offers,
        )
