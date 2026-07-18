"""Bounded live verification for the Mac Ctrip collector workflow."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import os
import sys
import time
from typing import Any
from urllib.parse import urlsplit

import httpx

from backend.application.services.flight_query import (
    FlightQuery,
    FlightQueryValidationError,
    build_flight_query,
)


TRACE_NAMES = (
    "ctrip_collector_claim",
    "ctrip_local_collect",
    "ctrip_collector_ingest",
    "flight_search",
)


class VerificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class VerifiedFare:
    price: int
    currency: str
    job_status: str


def _bounded_float(minimum: float, maximum: float):
    def parse(value: str) -> float:
        try:
            number = float(value)
        except ValueError as exc:
            raise argparse.ArgumentTypeError("must be a number") from exc
        if not minimum <= number <= maximum:
            raise argparse.ArgumentTypeError(
                f"must be between {minimum:g} and {maximum:g}"
            )
        return number

    return parse


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify one live FareSniper Ctrip route without printing secrets."
    )
    parser.add_argument("--base-url", default=os.getenv("FARESNIPER_API_URL", ""))
    parser.add_argument("--origin", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--depart-date", required=True)
    parser.add_argument(
        "--timeout-seconds",
        type=_bounded_float(1, 600),
        default=180.0,
    )
    parser.add_argument(
        "--poll-seconds",
        type=_bounded_float(0.05, 30),
        default=5.0,
    )
    parser.add_argument("--require-fresh", action="store_true")
    return parser


def _normalized_base_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    parsed = urlsplit(normalized)
    local_http = parsed.scheme == "http" and parsed.hostname in {
        "127.0.0.1",
        "localhost",
    }
    if (
        not parsed.hostname
        or (parsed.scheme != "https" and not local_http)
        or parsed.username is not None
        or parsed.password is not None
        or parsed.path not in {"", "/"}
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("base URL must be HTTPS (localhost HTTP is allowed)")
    return normalized


def _required_secret(name: str) -> str:
    value = os.getenv(name, "")
    if not value or any(character.isspace() for character in value):
        raise ValueError("required verification credentials are not configured")
    return value


def _ctrip_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for deal in payload.get("deals") or []:
        if not isinstance(deal, dict):
            continue
        for row in deal.get("prices") or []:
            if not isinstance(row, dict):
                continue
            if row.get("data_provider") != "ctrip_snapshot":
                continue
            price = row.get("price")
            url = row.get("url")
            parsed = urlsplit(url) if isinstance(url, str) else None
            if (
                isinstance(price, int)
                and not isinstance(price, bool)
                and price > 0
                and parsed is not None
                and parsed.scheme == "https"
                and parsed.hostname == "flights.ctrip.com"
            ):
                rows.append(row)
    return rows


def _is_fresh(row: dict[str, Any]) -> bool:
    return (
        row.get("data_freshness") == "fresh"
        and row.get("provider_status") == "success"
    )


def _validate_grounding(payload: dict[str, Any]) -> int:
    analysis = payload.get("analysis")
    minimum = analysis.get("min_price") if isinstance(analysis, dict) else None
    if not isinstance(minimum, int) or isinstance(minimum, bool) or minimum <= 0:
        raise VerificationError("search response has no numeric minimum price")

    card_prices: list[int] = []
    for deal in payload.get("deals") or []:
        if not isinstance(deal, dict):
            continue
        for candidate in (deal.get("price"), deal.get("lowest_price")):
            if isinstance(candidate, int) and not isinstance(candidate, bool):
                card_prices.append(candidate)
        for row in deal.get("prices") or []:
            candidate = row.get("price") if isinstance(row, dict) else None
            if isinstance(candidate, int) and not isinstance(candidate, bool):
                card_prices.append(candidate)
    recommendation = payload.get("recommendation")
    text = recommendation.get("text") if isinstance(recommendation, dict) else ""
    if minimum not in card_prices or not isinstance(text, str):
        raise VerificationError("card and recommendation facts are not grounded")
    if f"¥{minimum}" not in text or f"CNY {minimum}" not in text:
        raise VerificationError("card and recommendation prices do not match")
    return minimum


async def _request_json(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    headers: dict[str, str],
    params: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    response = await client.request(
        method,
        path,
        headers=headers,
        params=params,
        json=json_body,
    )
    if response.status_code >= 400:
        raise VerificationError(
            f"backend request failed with HTTP {response.status_code}"
        )
    try:
        payload = response.json()
    except ValueError as exc:
        raise VerificationError("backend returned invalid JSON") from exc
    if not isinstance(payload, dict):
        raise VerificationError("backend returned an invalid response")
    return payload


async def verify(
    *,
    base_url: str,
    query: FlightQuery,
    jwt_token: str,
    collector_token: str,
    timeout_seconds: float,
    poll_seconds: float,
    require_fresh: bool,
) -> VerifiedFare:
    deadline = time.monotonic() + timeout_seconds
    collector_headers = {"Authorization": f"Bearer {collector_token}"}
    search_headers = {"Authorization": f"Bearer {jwt_token}"}
    status_params = {
        "origin_code": query.origin_code,
        "destination_code": query.destination_code,
        "depart_date": query.depart_date,
    }
    message = (
        f"{query.depart_date} {query.origin_city}到"
        f"{query.destination_city}的机票"
    )

    async with httpx.AsyncClient(
        base_url=base_url,
        timeout=min(15.0, timeout_seconds),
        follow_redirects=False,
        trust_env=urlsplit(base_url).hostname not in {"127.0.0.1", "localhost"},
    ) as client:
        status_payload = await _request_json(
            client,
            "GET",
            "/internal/collector/status",
            headers=collector_headers,
            params=status_params,
        )
        if status_payload.get("collector_online") is not True:
            raise VerificationError("Mac collector heartbeat is offline")

        while True:
            search_payload = await _request_json(
                client,
                "POST",
                "/api/search",
                headers=search_headers,
                json_body={"session_id": None, "message": message},
            )
            status_payload = await _request_json(
                client,
                "GET",
                "/internal/collector/status",
                headers=collector_headers,
                params=status_params,
            )
            rows = _ctrip_rows(search_payload)
            eligible = [row for row in rows if _is_fresh(row)] if require_fresh else rows
            if status_payload.get("job_status") == "completed" and eligible:
                minimum = _validate_grounding(search_payload)
                selected = min(eligible, key=lambda row: int(row["price"]))
                return VerifiedFare(
                    price=int(selected["price"]),
                    currency=str(selected.get("currency") or "CNY"),
                    job_status="completed",
                )
            if time.monotonic() >= deadline:
                if require_fresh and rows:
                    raise VerificationError("fresh Ctrip price not observed")
                raise VerificationError("Ctrip collector job did not complete in time")
            await asyncio.sleep(min(poll_seconds, max(0.0, deadline - time.monotonic())))


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        query = build_flight_query(args.origin, args.destination, args.depart_date)
        base_url = _normalized_base_url(args.base_url)
        jwt_token = _required_secret("FARESNIPER_VERIFY_JWT")
        collector_token = _required_secret("CTRIP_COLLECTOR_TOKEN")
    except (FlightQueryValidationError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        result = asyncio.run(
            verify(
                base_url=base_url,
                query=query,
                jwt_token=jwt_token,
                collector_token=collector_token,
                timeout_seconds=args.timeout_seconds,
                poll_seconds=args.poll_seconds,
                require_fresh=args.require_fresh,
            )
        )
    except VerificationError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except (httpx.HTTPError, TimeoutError):
        print("backend verification request failed", file=sys.stderr)
        return 1

    print("collector=online")
    print(f"job={result.job_status}")
    print(f"ctrip_price={result.currency} {result.price}")
    print("langsmith_traces=" + ",".join(TRACE_NAMES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
