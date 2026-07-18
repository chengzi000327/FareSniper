from __future__ import annotations

import hashlib
from collections.abc import Mapping
from datetime import datetime, timezone
from math import inf
from typing import Any

from backend.application.contracts.flight_provider import (
    FlightOffer,
    FlightQuery,
    PriceStatus,
    ProviderResult,
    ProviderStatus,
)


_PROVIDER_PRIORITY = {
    "ctrip": 0,
    "ctrip_snapshot": 0,
    "flyai": 1,
    "serpapi": 2,
    "serpapi_google_flights": 2,
}
_PROVIDER_LABELS = {
    "ctrip": "携程",
    "flyai": "飞猪",
    "serpapi": "Google Flights",
}
_STATUS_DATA_PROVIDERS = {
    "ctrip": "ctrip_snapshot",
    "flyai": "flyai",
    "serpapi": "serpapi_google_flights",
}


def _identity(
    offer: FlightOffer,
) -> tuple[str, str, str, str, str, str, str]:
    return (
        offer.origin_code,
        offer.origin_airport_code or "",
        offer.destination_code,
        offer.destination_airport_code or "",
        offer.depart_date,
        offer.flight_no,
        offer.depart_time,
    )


def _card_id(identity: tuple[str, ...]) -> str:
    return hashlib.sha1("|".join(identity).encode("utf-8")).hexdigest()[:16]


def _row_id(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode("utf-8")).hexdigest()[:16]


def _is_fresh_numeric(offer: FlightOffer) -> bool:
    return (
        isinstance(offer.total_price, int)
        and offer.price_status is not PriceStatus.stale
    )


def _parse_offer_expiry(value: object) -> tuple[datetime | None, bool]:
    if value is None:
        return None, False
    if not isinstance(value, str) or not value.strip():
        return None, True
    try:
        expiry = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None, True
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    return expiry.astimezone(timezone.utc), False


def _normalized_offer_expiry(value: object) -> str | None:
    expiry, malformed = _parse_offer_expiry(value)
    if malformed or expiry is None:
        return None
    return expiry.isoformat()


def _offer_freshness(
    offer: FlightOffer,
    provider_status: ProviderStatus,
    *,
    now: datetime,
) -> str:
    if (
        provider_status is ProviderStatus.stale
        or offer.price_status is PriceStatus.stale
    ):
        return "stale"
    if provider_status is not ProviderStatus.success:
        return "unknown"
    expiry, malformed_expiry = _parse_offer_expiry(offer.expires_at)
    if malformed_expiry:
        return "unknown"
    if expiry is not None:
        return "stale" if expiry <= now else "fresh"
    if offer.is_realtime:
        return "fresh"
    return "unknown"


def _is_ctrip_candidate(
    offer: FlightOffer,
    provider_status: ProviderStatus,
    *,
    now: datetime,
) -> bool:
    if (
        offer.data_provider == "ctrip_snapshot"
        and isinstance(offer.total_price, int)
        and offer.booking_url is not None
    ):
        freshness = _offer_freshness(offer, provider_status, now=now)
        return (
            provider_status is ProviderStatus.success
            and offer.price_status is PriceStatus.priced
            and freshness == "fresh"
        ) or (
            provider_status is ProviderStatus.stale
            and offer.price_status is PriceStatus.stale
            and freshness == "stale"
        )
    return False


def _is_ranked_offer(
    offer: FlightOffer,
    provider_status: ProviderStatus,
    *,
    now: datetime,
) -> bool:
    is_fresh_realtime = (
        offer.is_realtime
        and _is_fresh_numeric(offer)
        and _offer_freshness(offer, provider_status, now=now) == "fresh"
    )
    return is_fresh_realtime or _is_ctrip_candidate(
        offer, provider_status, now=now
    )


def _price_row(
    offer: FlightOffer,
    provider_status: ProviderStatus,
    *,
    now: datetime,
) -> dict[str, Any]:
    return {
        "id": _row_id(
            offer.data_provider, offer.seller_name, offer.currency
        ),
        "name": offer.seller_name,
        "price": offer.total_price,
        "currency": offer.currency,
        "lowest": False,
        "price_status": offer.price_status.value,
        "provider_status": provider_status.value,
        "url": offer.booking_url,
        "data_provider": offer.data_provider,
        "data_freshness": _offer_freshness(
            offer, provider_status, now=now
        ),
        "expires_at": _normalized_offer_expiry(offer.expires_at),
    }


def _status_row(
    provider: str, result: ProviderResult, currency: str
) -> dict[str, Any]:
    data_provider = _STATUS_DATA_PROVIDERS.get(provider, provider)
    return {
        "id": _row_id(data_provider, provider, currency),
        "name": _PROVIDER_LABELS.get(provider, provider),
        "price": None,
        "currency": currency,
        "lowest": False,
        "price_status": None,
        "provider_status": result.status.value,
        "url": None,
        "data_provider": data_provider,
        "data_freshness": (
            "stale"
            if result.status is ProviderStatus.stale
            else "unknown"
        ),
        "expires_at": None,
    }


def _row_sort_key(row: dict[str, Any]) -> tuple[float, str, float, str]:
    provider = str(row.get("data_provider", ""))
    price = row.get("price")
    numeric_price = float(price) if isinstance(price, int) else inf
    return (
        float(_PROVIDER_PRIORITY.get(provider, 2)),
        str(row.get("currency", "")),
        numeric_price,
        str(row.get("name", "")),
    )


def _fetched_at_rank(value: str | None) -> float:
    if not value:
        return inf
    try:
        fetched_at = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return inf
    if fetched_at.tzinfo is None:
        fetched_at = fetched_at.replace(tzinfo=timezone.utc)
    return -fetched_at.timestamp()


def _offer_dedupe_key(
    offer: FlightOffer,
    provider_status: ProviderStatus,
    *,
    now: datetime,
) -> tuple[int, float, float, str]:
    numeric_price = (
        float(offer.total_price)
        if isinstance(offer.total_price, int)
        else inf
    )
    return (
        0
        if _is_fresh_numeric(offer)
        and _offer_freshness(offer, provider_status, now=now) == "fresh"
        else 1,
        numeric_price,
        _fetched_at_rank(offer.fetched_at),
        offer.booking_url or "",
    )


def _deduplicate_rows(
    offers: list[tuple[FlightOffer, ProviderStatus]],
    *,
    now: datetime,
) -> list[tuple[FlightOffer, ProviderStatus]]:
    grouped: dict[
        tuple[str, str, str], tuple[FlightOffer, ProviderStatus]
    ] = {}
    for offer, provider_status in offers:
        key = (offer.data_provider, offer.seller_name, offer.currency)
        current = grouped.get(key)
        if current is None or _offer_dedupe_key(
            offer, provider_status, now=now
        ) < _offer_dedupe_key(
            current[0], current[1], now=now
        ):
            grouped[key] = (offer, provider_status)
    return list(grouped.values())


def _select_ranked_offer(
    offers: list[tuple[FlightOffer, ProviderStatus]],
    preferred_currency: str,
    *,
    now: datetime,
) -> tuple[FlightOffer, ProviderStatus] | None:
    ranked = [
        (offer, provider_status)
        for offer, provider_status in offers
        if _is_ranked_offer(offer, provider_status, now=now)
    ]
    if not ranked:
        return None
    preferred = [
        item for item in ranked if item[0].currency == preferred_currency
    ]
    if preferred:
        candidates = preferred
    else:
        selected_currency = min(
            {offer.currency for offer, _ in ranked},
            key=lambda currency: (
                min(
                    _PROVIDER_PRIORITY.get(offer.data_provider, 2)
                    for offer, _ in ranked
                    if offer.currency == currency
                ),
                currency,
            ),
        )
        candidates = [
            item for item in ranked if item[0].currency == selected_currency
        ]
    return min(
        candidates,
        key=lambda item: (
            item[0].total_price
            if isinstance(item[0].total_price, int)
            else inf,
            _PROVIDER_PRIORITY.get(item[0].data_provider, 2),
            item[0].seller_name,
        ),
    )


def _winning_row_id(offer: FlightOffer) -> str:
    return _row_id(offer.data_provider, offer.seller_name, offer.currency)


def _apply_ranked_offer(
    card: dict[str, Any],
    offer: FlightOffer,
    provider_status: ProviderStatus,
    *,
    now: datetime,
) -> None:
    card.update(
        {
            "airline": offer.airline,
            "platform": offer.seller_name,
            "depart_time": offer.depart_time,
            "arrive_time": offer.arrive_time,
            "duration_minutes": offer.duration_minutes,
            "stops": offer.stops,
            "price": offer.total_price,
            "lowest_price": offer.total_price,
            "tax": offer.tax,
            "baggage_fee": offer.baggage_fee,
            "has_baggage": offer.has_baggage,
            "total_price": offer.total_price,
            "currency": offer.currency,
            "cabin": offer.cabin,
            "booking_url": offer.booking_url,
            "h5_fallback_url": offer.booking_url,
            "winning_price_id": _winning_row_id(offer),
            "data_freshness": _offer_freshness(
                offer, provider_status, now=now
            ),
            "inventory_expires_at": _normalized_offer_expiry(
                offer.expires_at
            ),
        }
    )


def _new_card(offer: FlightOffer) -> dict[str, Any]:
    identity = _identity(offer)
    return {
        "id": _card_id(identity),
        "system_id": "-".join(
            (offer.flight_no, offer.depart_date, offer.depart_time)
        ),
        "flight_no": offer.flight_no,
        "airline": offer.airline,
        "platform": "",
        "origin_city": offer.origin_city,
        "origin_code": offer.origin_code,
        "origin_airport_code": offer.origin_airport_code,
        "destination_city": offer.destination_city,
        "destination_code": offer.destination_code,
        "destination_airport_code": offer.destination_airport_code,
        "depart_date": offer.depart_date,
        "depart_time": offer.depart_time,
        "arrive_time": offer.arrive_time,
        "duration_minutes": offer.duration_minutes,
        "stops": offer.stops,
        "price": None,
        "lowest_price": None,
        "tax": None,
        "baggage_fee": None,
        "has_baggage": None,
        "total_price": None,
        "currency": offer.currency,
        "recommend_score": None,
        "cabin": offer.cabin,
        "booking_url": None,
        "h5_fallback_url": None,
        "winning_price_id": None,
        "data_freshness": "unknown",
        "inventory_expires_at": None,
        "prices": [],
        "signals": [],
        "confidence": "medium",
        "verdict": "",
    }


def offers_to_deals(
    query: FlightQuery,
    results: Mapping[str, ProviderResult],
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    pass_now = now or datetime.now(timezone.utc)
    if pass_now.tzinfo is None:
        pass_now = pass_now.replace(tzinfo=timezone.utc)
    else:
        pass_now = pass_now.astimezone(timezone.utc)
    cards: dict[tuple[str, str, str, str, str, str, str], dict[str, Any]] = {}
    card_offers: dict[
        tuple[str, str, str, str, str, str, str],
        list[tuple[FlightOffer, ProviderStatus]],
    ] = {}

    for result in results.values():
        for offer in result.offers:
            identity = _identity(offer)
            cards.setdefault(identity, _new_card(offer))
            card_offers.setdefault(identity, []).append(
                (offer, result.status)
            )

    status_rows = [
        _status_row(provider, result, query.currency)
        for provider, result in results.items()
        if not result.offers
    ]
    for identity, card in cards.items():
        deduplicated = _deduplicate_rows(
            card_offers[identity], now=pass_now
        )
        ranked_offer = _select_ranked_offer(
            deduplicated, query.currency, now=pass_now
        )
        if ranked_offer is not None:
            _apply_ranked_offer(card, *ranked_offer, now=pass_now)

        rows = [
            _price_row(offer, provider_status, now=pass_now)
            for offer, provider_status in deduplicated
        ]
        rows.extend(dict(row) for row in status_rows)
        for row in rows:
            row["lowest"] = row["id"] == card["winning_price_id"]
        rows.sort(key=_row_sort_key)
        card["prices"] = rows

    return list(cards.values())


def rank_deals(
    deals: list[dict[str, Any]], preferred_currency: str | None = None
) -> list[dict[str, Any]]:
    def currency_key(deal: dict[str, Any]) -> tuple[int, str]:
        currency = str(deal.get("currency", ""))
        if preferred_currency and currency == preferred_currency:
            return 0, ""
        return 1, currency

    return sorted(
        deals,
        key=lambda deal: (
            *currency_key(deal),
            deal["total_price"]
            if isinstance(deal.get("total_price"), int)
            else inf,
            deal.get("stops", 0),
            deal.get("depart_time", ""),
        ),
    )
