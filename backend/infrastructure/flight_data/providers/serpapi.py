from __future__ import annotations

import asyncio
import random
import re
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from urllib.parse import urlparse

import httpx

from backend.application.contracts.flight_provider import (
    FlightOffer,
    FlightQuery,
    PriceStatus,
    ProviderResult,
    ProviderStatus,
)


_SEARCH_URL = "https://serpapi.com/search.json"
_TIMEOUT_SECONDS = 10.0


@dataclass(frozen=True)
class _GetFailure:
    error_code: str


def _is_https_url(value: object) -> bool:
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)


def _parse_price(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    cleaned = re.sub(r"[^0-9.+-]", "", str(value))
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
    return text.split(" ", 1)[-1][:5]


def _parse_currency(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    currency = value.strip().upper()
    return currency if len(currency) == 3 and currency.isalpha() else None


def _payload_currency(payload: Mapping[str, object]) -> str | None:
    direct = _parse_currency(payload.get("currency"))
    if direct:
        return direct
    search_parameters = payload.get("search_parameters")
    if isinstance(search_parameters, Mapping):
        return _parse_currency(search_parameters.get("currency"))
    return None


def _booking_details(
    payload: Mapping[str, object],
) -> tuple[str | None, int | None, str | None, str | None]:
    options = payload.get("booking_options")
    if not isinstance(options, list) or not options:
        return None, None, None, _payload_currency(payload)
    first_option = options[0]
    if not isinstance(first_option, Mapping):
        return None, None, None, _payload_currency(payload)
    together = first_option.get("together")
    if not isinstance(together, Mapping):
        return None, None, None, _payload_currency(payload)

    booking_request = together.get("booking_request")
    booking_url = None
    if isinstance(booking_request, Mapping) and "post_data" not in booking_request:
        url = booking_request.get("url")
        booking_url = url if _is_https_url(url) else None
    seller = together.get("book_with")
    return (
        seller if isinstance(seller, str) and seller else None,
        _parse_price(together.get("price")),
        booking_url,
        _parse_currency(together.get("currency"))
        or _payload_currency(payload),
    )


class SerpApiProvider:
    name = "serpapi"

    def __init__(self, *, api_key: str, client: httpx.AsyncClient | None = None):
        self._api_key = api_key
        self._client = client or httpx.AsyncClient(timeout=_TIMEOUT_SECONDS)

    def supports(self, query: FlightQuery) -> bool:
        return not query.is_mainland_domestic

    @staticmethod
    def _error_result(error_code: str) -> ProviderResult:
        return ProviderResult(
            provider=SerpApiProvider.name,
            status=ProviderStatus.error,
            error_code=error_code,
        )

    async def _get(
        self, params: Mapping[str, str]
    ) -> httpx.Response | _GetFailure:
        for attempt in range(2):
            try:
                response = await self._client.get(
                    _SEARCH_URL, params=params, timeout=_TIMEOUT_SECONDS
                )
            except httpx.TransportError:
                if attempt == 0:
                    await asyncio.sleep(random.uniform(0.05, 0.25))
                    continue
                return _GetFailure("network")

            if response.status_code in (401, 403):
                return _GetFailure("authentication")
            if response.status_code == 429:
                if attempt == 0:
                    await asyncio.sleep(random.uniform(0.05, 0.25))
                    continue
                return _GetFailure("rate_limited")
            if response.status_code >= 500:
                if attempt == 0:
                    await asyncio.sleep(random.uniform(0.05, 0.25))
                    continue
                return _GetFailure("upstream_http")
            if response.is_error:
                return _GetFailure("upstream_http")
            return response
        return _GetFailure("upstream_http")

    def _search_params(self, query: FlightQuery) -> dict[str, str]:
        return {
            "engine": "google_flights",
            "departure_id": ",".join(query.origin_airport_ids),
            "arrival_id": ",".join(query.destination_airport_ids),
            "outbound_date": query.depart_date,
            "type": "2",
            "currency": query.currency,
            "hl": "zh-cn",
            "gl": "cn",
            "sort_by": "2",
            "adults": "1",
            "api_key": self._api_key,
        }

    async def _booking_options(self, token: str) -> Mapping[str, object] | None:
        response = await self._get(
            {
                "engine": "google_flights_booking_options",
                "booking_token": token,
                "api_key": self._api_key,
            }
        )
        if isinstance(response, _GetFailure):
            return None
        try:
            payload = response.json()
        except (ValueError, httpx.DecodingError):
            return None
        return payload if isinstance(payload, Mapping) else None

    @staticmethod
    def _itineraries(payload: Mapping[str, object]) -> list[Mapping[str, object]]:
        itineraries: list[Mapping[str, object]] = []
        for key in ("best_flights", "other_flights"):
            value = payload.get(key)
            if isinstance(value, list):
                itineraries.extend(item for item in value if isinstance(item, Mapping))
        return itineraries

    async def search(self, query: FlightQuery) -> ProviderResult:
        if not self._api_key:
            return ProviderResult(provider=self.name, status=ProviderStatus.disabled)
        if not self.supports(query):
            return ProviderResult(provider=self.name, status=ProviderStatus.empty)

        response = await self._get(self._search_params(query))
        if isinstance(response, _GetFailure):
            return self._error_result(response.error_code)
        try:
            payload = response.json()
        except (ValueError, httpx.DecodingError):
            return self._error_result("upstream_response")
        if not isinstance(payload, Mapping):
            return self._error_result("upstream_response")
        response_currency = _payload_currency(payload) or query.currency

        metadata = payload.get("search_metadata")
        google_flights_url = (
            metadata.get("google_flights_url")
            if isinstance(metadata, Mapping)
            else None
        )
        fallback_url = google_flights_url if _is_https_url(google_flights_url) else None
        itineraries = self._itineraries(payload)
        booking_indices = sorted(
            (
                index
                for index, itinerary in enumerate(itineraries)
                if isinstance(itinerary.get("booking_token"), str)
                and itinerary["booking_token"]
            ),
            key=lambda index: (
                _parse_price(itineraries[index].get("price")) is None,
                _parse_price(itineraries[index].get("price")) or 0,
            ),
        )[:3]
        booking_payloads = await asyncio.gather(
            *(
                self._booking_options(itineraries[index]["booking_token"])
                for index in booking_indices
            )
        )
        bookings = dict(zip(booking_indices, booking_payloads))

        offers: list[FlightOffer] = []
        for index, itinerary in enumerate(itineraries):
            flights = itinerary.get("flights")
            if not isinstance(flights, list):
                continue
            legs = [leg for leg in flights if isinstance(leg, Mapping)]
            if not legs:
                continue
            first_leg = legs[0]
            last_leg = legs[-1]
            seller, booking_price, booking_url, booking_currency = (
                _booking_details(bookings[index])
                if isinstance(bookings.get(index), Mapping)
                else (None, None, None, None)
            )
            ticket_sellers = first_leg.get("ticket_also_sold_by")
            ticket_seller = (
                ticket_sellers[0]
                if isinstance(ticket_sellers, list)
                and ticket_sellers
                and isinstance(ticket_sellers[0], str)
                else None
            )
            airline = first_leg.get("airline")
            airline_name = airline if isinstance(airline, str) else ""
            price = booking_price if booking_price is not None else _parse_price(itinerary.get("price"))
            currency = (
                booking_currency
                if booking_price is not None and booking_currency
                else _payload_currency(itinerary) or response_currency
            )
            url = booking_url or fallback_url
            if price is None and url is None:
                continue
            offers.append(
                FlightOffer(
                    data_provider="serpapi_google_flights",
                    seller_name=seller or ticket_seller or airline_name or "Google Flights",
                    flight_no="/".join(
                        str(leg["flight_number"])
                        for leg in legs
                        if leg.get("flight_number")
                    ),
                    airline="/".join(
                        str(leg["airline"]) for leg in legs if leg.get("airline")
                    ),
                    origin_city=query.origin_city,
                    origin_code=query.origin_code,
                    destination_city=query.destination_city,
                    destination_code=query.destination_code,
                    depart_date=query.depart_date,
                    depart_time=_time_part(
                        first_leg.get("departure_airport", {}).get("time")
                        if isinstance(first_leg.get("departure_airport"), Mapping)
                        else None
                    ),
                    arrive_time=_time_part(
                        last_leg.get("arrival_airport", {}).get("time")
                        if isinstance(last_leg.get("arrival_airport"), Mapping)
                        else None
                    ),
                    duration_minutes=(
                        int(first_leg["duration"])
                        if isinstance(first_leg.get("duration"), (int, float))
                        and not isinstance(first_leg.get("duration"), bool)
                        else None
                    ),
                    stops=max(0, len(legs) - 1),
                    cabin=(
                        first_leg.get("travel_class")
                        if isinstance(first_leg.get("travel_class"), str)
                        else None
                    ),
                    currency=currency,
                    total_price=price,
                    tax=None,
                    baggage_fee=None,
                    has_baggage=None,
                    price_status=(
                        PriceStatus.priced
                        if price is not None
                        else PriceStatus.view_live_price
                    ),
                    booking_url=url,
                )
            )

        return ProviderResult(
            provider=self.name,
            status=ProviderStatus.success if offers else ProviderStatus.empty,
            offers=offers,
        )
