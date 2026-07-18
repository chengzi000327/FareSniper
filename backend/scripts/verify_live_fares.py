"""Bounded live verification for the Mac Ctrip collector workflow."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
import os
import re
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


def _positive_int(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _validate_response_query(
    payload: dict[str, Any], query: FlightQuery
) -> None:
    response_query = payload.get("query")
    if not isinstance(response_query, dict) or (
        response_query.get("origin_code"),
        response_query.get("destination_code"),
        response_query.get("date_start"),
    ) != (
        query.origin_code,
        query.destination_code,
        query.depart_date,
    ):
        raise VerificationError("search response query does not match request")


def _valid_ctrip_row(row: object) -> dict[str, Any] | None:
    if not isinstance(row, dict) or row.get("data_provider") != "ctrip_snapshot":
        return None
    price = _positive_int(row.get("price"))
    url = row.get("url")
    try:
        parsed = urlsplit(url) if isinstance(url, str) else None
    except ValueError:
        return None
    if (
        price is None
        or parsed is None
        or parsed.scheme != "https"
        or parsed.hostname != "flights.ctrip.com"
        or parsed.username is not None
        or parsed.password is not None
    ):
        return None
    return row


def _is_fresh(row: dict[str, Any]) -> bool:
    return (
        row.get("data_freshness") == "fresh"
        and row.get("provider_status") == "success"
    )


def _recommendation_has_amount(text: str, currency: str, price: int) -> bool:
    token = f"¥{price}" if currency == "CNY" else f"{currency} {price}"
    return re.search(rf"(?<!\d){re.escape(token)}(?!\d)", text) is not None


def _validate_final_response(
    payload: dict[str, Any],
    query: FlightQuery,
    *,
    require_fresh: bool,
) -> tuple[int, str]:
    _validate_response_query(payload, query)
    analysis = payload.get("analysis")
    minimum = (
        _positive_int(analysis.get("min_price"))
        if isinstance(analysis, dict)
        else None
    )
    if minimum is None:
        raise VerificationError("search response has no numeric minimum price")

    selected: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    for deal in payload.get("deals") or []:
        if not isinstance(deal, dict):
            continue
        ctrip_rows = [
            valid
            for row in deal.get("prices") or []
            if (valid := _valid_ctrip_row(row)) is not None
        ]
        if not ctrip_rows:
            continue
        if (
            deal.get("origin_code"),
            deal.get("destination_code"),
            deal.get("depart_date"),
        ) != (
            query.origin_code,
            query.destination_code,
            query.depart_date,
        ):
            raise VerificationError("Ctrip deal scope does not match request")
        for row in ctrip_rows:
            for field, expected in (
                ("origin_code", query.origin_code),
                ("destination_code", query.destination_code),
                ("depart_date", query.depart_date),
            ):
                if field in row and row[field] != expected:
                    raise VerificationError(
                        "Ctrip deal scope does not match request"
                    )
        if _positive_int(deal.get("price")) == minimum:
            selected.append((deal, ctrip_rows))

    if not selected:
        raise VerificationError(
            "displayed card price does not match analysis minimum"
        )

    deal, ctrip_rows = selected[0]
    for field in ("lowest_price", "total_price"):
        value = deal.get(field)
        if value is not None and _positive_int(value) != minimum:
            raise VerificationError(
                "displayed card price does not match analysis minimum"
            )
    eligible = (
        [row for row in ctrip_rows if _is_fresh(row)]
        if require_fresh
        else ctrip_rows
    )
    if not eligible:
        if require_fresh:
            raise VerificationError("fresh Ctrip price not observed")
        raise VerificationError("scoped Ctrip price not observed")

    recommendation = payload.get("recommendation")
    text = recommendation.get("text") if isinstance(recommendation, dict) else ""
    currency = str(deal.get("currency") or "").upper()
    if (
        not isinstance(text, str)
        or not currency
        or not _recommendation_has_amount(text, currency, minimum)
    ):
        raise VerificationError(
            "recommendation price does not match displayed card"
        )
    ctrip_row = min(eligible, key=lambda row: int(row["price"]))
    return int(ctrip_row["price"]), str(ctrip_row.get("currency") or currency)


def _remaining_seconds(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise VerificationError("verification timed out")
    return remaining


async def _request_json(
    client: httpx.AsyncClient,
    method: str,
    path: str,
    *,
    headers: dict[str, str],
    params: dict[str, str] | None = None,
    json_body: dict[str, Any] | None = None,
    deadline: float,
) -> dict[str, Any]:
    remaining = _remaining_seconds(deadline)
    try:
        async with asyncio.timeout(remaining):
            response = await client.request(
                method,
                path,
                headers=headers,
                params=params,
                json=json_body,
                timeout=httpx.Timeout(remaining),
            )
    except (TimeoutError, httpx.TimeoutException) as exc:
        raise VerificationError("verification timed out") from exc
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
    transport: httpx.AsyncBaseTransport | None = None,
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

    try:
        async with asyncio.timeout(timeout_seconds):
            async with httpx.AsyncClient(
                base_url=base_url,
                timeout=None,
                follow_redirects=False,
                transport=transport,
                trust_env=(
                    False
                    if transport is not None
                    else urlsplit(base_url).hostname
                    not in {"127.0.0.1", "localhost"}
                ),
            ) as client:
                status_payload = await _request_json(
                    client,
                    "GET",
                    "/internal/collector/status",
                    headers=collector_headers,
                    params=status_params,
                    deadline=deadline,
                )
                if status_payload.get("collector_online") is not True:
                    raise VerificationError(
                        "Mac collector heartbeat is offline"
                    )

                await _request_json(
                    client,
                    "POST",
                    "/api/search",
                    headers=search_headers,
                    json_body={"session_id": None, "message": message},
                    deadline=deadline,
                )

                while True:
                    status_payload = await _request_json(
                        client,
                        "GET",
                        "/internal/collector/status",
                        headers=collector_headers,
                        params=status_params,
                        deadline=deadline,
                    )
                    if status_payload.get("job_status") == "completed":
                        break
                    await asyncio.sleep(
                        min(poll_seconds, _remaining_seconds(deadline))
                    )

                final_payload = await _request_json(
                    client,
                    "POST",
                    "/api/search",
                    headers=search_headers,
                    json_body={"session_id": None, "message": message},
                    deadline=deadline,
                )
                ctrip_price, currency = _validate_final_response(
                    final_payload,
                    query,
                    require_fresh=require_fresh,
                )
                return VerifiedFare(
                    price=ctrip_price,
                    currency=currency,
                    job_status="completed",
                )
    except TimeoutError as exc:
        raise VerificationError("verification timed out") from exc


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
