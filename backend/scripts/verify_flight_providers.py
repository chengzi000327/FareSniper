"""Run an explicit live-provider smoke check and print a redacted summary."""

from __future__ import annotations

import argparse
import asyncio
import hmac
import json
import re
import sys
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any

from backend.application.contracts.flight_provider import ProviderStatus
from backend.application.services.flight_query import (
    FlightQueryValidationError,
    build_flight_query,
)
from backend.application.services.flight_search_aggregator import (
    FlightSearchAggregator,
)
from backend.config import settings
from backend.infrastructure.flight_data.providers.factory import (
    build_flight_providers,
)


_ALLOWED_PROVIDERS = ("flyai", "ctrip", "serpapi")
_ALLOWED_STATUSES = {status.value for status in ProviderStatus}
_USABLE_STATUSES = {ProviderStatus.success.value, ProviderStatus.empty.value}
_SELLER_PATTERN = re.compile(
    r"^[A-Za-z0-9\u3400-\u9fff][A-Za-z0-9\u3400-\u9fff .&'()\-]{0,79}$"
)
_OPAQUE_SELLER_PATTERN = re.compile(r"^[A-Za-z0-9_-]{24,}$")
_SENSITIVE_SELLER_MARKERS = ("www.", "sk-", "lsv2_", "token", "secret", "auth", "bearer")
_SECRET_SETTING_NAMES = (
    "flyai_api_key",
    "serpapi_api_key",
    "variflight_api_key",
    "langsmith_api_key",
    "langchain_api_key",
    "model_api_key",
    "llm_api_key",
    "jwt_secret",
    "sms_aliyun_access_key_id",
    "sms_twilio_sid",
    "sms_twilio_token",
    "vapid_private_key",
    "flight_status_api_key",
)
_EMPTY_SUMMARY = {
    "provider_statuses": {},
    "deal_count": 0,
    "sellers": [],
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Verify configured flight providers with a safe JSON summary."
    )
    parser.add_argument("--origin", required=True)
    parser.add_argument("--destination", required=True)
    parser.add_argument("--depart-date", required=True)
    return parser


def _canonical_query(origin: str, destination: str, depart_date: str):
    try:
        canonical_date = date.fromisoformat(depart_date).isoformat()
    except ValueError as exc:
        raise FlightQueryValidationError(
            "departure date must use canonical YYYY-MM-DD form"
        ) from exc
    if depart_date != canonical_date:
        raise FlightQueryValidationError(
            "departure date must use canonical YYYY-MM-DD form"
        )

    query = build_flight_query(origin, destination, depart_date)
    if origin != query.origin_city or destination != query.destination_city:
        raise FlightQueryValidationError(
            "origin and destination must be canonical full Chinese city names"
        )
    return query


def _safe_provider_statuses(value: Any) -> dict[str, str]:
    if not isinstance(value, Mapping):
        return {}

    statuses: dict[str, str] = {}
    for provider in _ALLOWED_PROVIDERS:
        status = value.get(provider)
        normalized = status.value if isinstance(status, ProviderStatus) else status
        if isinstance(normalized, str) and normalized in _ALLOWED_STATUSES:
            statuses[provider] = normalized
    return statuses


def _configured_secrets() -> tuple[str, ...]:
    return tuple(
        value
        for name in _SECRET_SETTING_NAMES
        if isinstance(value := getattr(settings, name, ""), str)
        and len(value) >= 8
    )


def _contains_configured_secret(value: str) -> bool:
    value_bytes = value.encode("utf-8")
    for secret in _configured_secrets():
        secret_bytes = secret.encode("utf-8")
        if len(secret_bytes) > len(value_bytes):
            continue
        for offset in range(len(value_bytes) - len(secret_bytes) + 1):
            candidate = value_bytes[offset : offset + len(secret_bytes)]
            if hmac.compare_digest(candidate, secret_bytes):
                return True
    return False


def _safe_seller(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    seller = value.strip()
    if not seller or _OPAQUE_SELLER_PATTERN.fullmatch(seller):
        return None
    if not _SELLER_PATTERN.fullmatch(seller):
        return None
    normalized = seller.casefold()
    if any(marker in normalized for marker in _SENSITIVE_SELLER_MARKERS):
        return None
    if re.search(r"(?:^|[ .&'()\-])key(?:$|[ .&'()\-])", normalized):
        return None
    if _contains_configured_secret(seller):
        return None
    return seller


def _safe_summary(result: Any) -> dict[str, Any]:
    if not isinstance(result, Mapping):
        return dict(_EMPTY_SUMMARY)

    deals = result.get("deals")
    safe_deals = (
        deals
        if isinstance(deals, Sequence) and not isinstance(deals, str)
        else []
    )
    sellers: set[str] = set()
    for deal in safe_deals:
        if not isinstance(deal, Mapping):
            continue
        platform = _safe_seller(deal.get("platform"))
        if platform:
            sellers.add(platform)
        prices = deal.get("prices")
        if not isinstance(prices, Sequence) or isinstance(prices, str):
            continue
        for price in prices:
            if isinstance(price, Mapping):
                seller = _safe_seller(price.get("name"))
                if seller:
                    sellers.add(seller)

    return {
        "provider_statuses": _safe_provider_statuses(
            result.get("provider_statuses")
        ),
        "deal_count": len(safe_deals),
        "sellers": sorted(sellers),
    }


async def _run(origin: str, destination: str, depart_date: str) -> dict[str, Any]:
    query = _canonical_query(origin, destination, depart_date)
    aggregator = FlightSearchAggregator(
        build_flight_providers(),
        timeout_seconds=settings.flight_provider_timeout_seconds,
    )
    return _safe_summary(await aggregator.collect(query))


def _print_summary(summary: Mapping[str, Any]) -> None:
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


def _has_usable_provider(summary: Mapping[str, Any]) -> bool:
    statuses = summary.get("provider_statuses")
    return isinstance(statuses, Mapping) and any(
        status in _USABLE_STATUSES for status in statuses.values()
    )


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        summary = asyncio.run(
            _run(args.origin, args.destination, args.depart_date)
        )
    except FlightQueryValidationError:
        _print_summary(_EMPTY_SUMMARY)
        print("Flight provider smoke check rejected invalid input.", file=sys.stderr)
        return 2
    except Exception:
        _print_summary(_EMPTY_SUMMARY)
        print("Flight provider smoke check failed.", file=sys.stderr)
        return 1

    _print_summary(summary)
    if not _has_usable_provider(summary):
        print(
            "Flight provider smoke check found no usable provider.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
