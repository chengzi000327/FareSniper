from __future__ import annotations

import hashlib
from collections.abc import Mapping
from math import inf
from typing import Any

from backend.application.contracts.flight_provider import (
    FlightOffer,
    FlightQuery,
    PriceStatus,
    ProviderResult,
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


def _identity(offer: FlightOffer) -> tuple[str, str, str, str, str]:
    return (
        offer.origin_code,
        offer.destination_code,
        offer.depart_date,
        offer.flight_no,
        offer.depart_time,
    )


def _card_id(identity: tuple[str, ...]) -> str:
    return hashlib.sha1("|".join(identity).encode("utf-8")).hexdigest()[:16]


def _is_fresh_numeric(offer: FlightOffer) -> bool:
    return (
        isinstance(offer.total_price, int)
        and offer.price_status is not PriceStatus.stale
    )


def _is_ranked_offer(offer: FlightOffer) -> bool:
    return offer.is_realtime and _is_fresh_numeric(offer)


def _price_row(offer: FlightOffer) -> dict[str, Any]:
    return {
        "name": offer.seller_name,
        "price": offer.total_price,
        "lowest": False,
        "status": offer.price_status.value,
        "url": offer.booking_url,
        "data_provider": offer.data_provider,
    }


def _status_row(provider: str, result: ProviderResult) -> dict[str, Any]:
    return {
        "name": _PROVIDER_LABELS.get(provider, provider),
        "price": None,
        "lowest": False,
        "status": result.status.value,
        "url": None,
        "data_provider": _STATUS_DATA_PROVIDERS.get(provider, provider),
    }


def _row_sort_key(row: dict[str, Any]) -> tuple[float, float]:
    provider = str(row.get("data_provider", ""))
    price = row.get("price")
    numeric_price = float(price) if isinstance(price, int) else inf
    return float(_PROVIDER_PRIORITY.get(provider, 2)), numeric_price


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
        "destination_city": offer.destination_city,
        "destination_code": offer.destination_code,
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
        "cabin": offer.cabin,
        "booking_url": None,
        "h5_fallback_url": None,
        "prices": [],
        "signals": [],
        "confidence": "medium",
        "verdict": "",
    }


def _apply_ranked_offer(card: dict[str, Any], offer: FlightOffer) -> None:
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
        }
    )


def offers_to_deals(
    query: FlightQuery,
    results: Mapping[str, ProviderResult],
) -> list[dict[str, Any]]:
    del query  # Offer identity carries the normalized route and date.
    cards: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    card_offers: dict[
        tuple[str, str, str, str, str], list[FlightOffer]
    ] = {}

    for result in results.values():
        for offer in result.offers:
            identity = _identity(offer)
            cards.setdefault(identity, _new_card(offer))
            card_offers.setdefault(identity, []).append(offer)

    status_rows = [
        _status_row(provider, result)
        for provider, result in results.items()
        if not result.offers
    ]
    for identity, card in cards.items():
        offers = card_offers[identity]
        ranked_offers = [offer for offer in offers if _is_ranked_offer(offer)]
        if ranked_offers:
            _apply_ranked_offer(
                card,
                min(
                    ranked_offers,
                    key=lambda offer: (
                        offer.total_price
                        if isinstance(offer.total_price, int)
                        else inf
                    ),
                ),
            )

        rows = [_price_row(offer) for offer in offers]
        rows.extend(dict(row) for row in status_rows)
        eligible_rows = [
            row
            for row in rows
            if isinstance(row.get("price"), int)
            and row.get("status") != PriceStatus.stale.value
        ]
        if eligible_rows:
            min(eligible_rows, key=lambda row: row["price"])["lowest"] = True
        rows.sort(key=_row_sort_key)
        card["prices"] = rows

    return list(cards.values())


def rank_deals(deals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        deals,
        key=lambda deal: (
            deal["total_price"]
            if isinstance(deal.get("total_price"), int)
            else inf,
            deal.get("stops", 0),
            deal.get("depart_time", ""),
        ),
    )
