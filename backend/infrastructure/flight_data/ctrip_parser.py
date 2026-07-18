from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from backend.application.contracts.flight_provider import (
    FlightOffer,
    FlightQuery,
    PriceStatus,
)
from backend.application.services.airport_catalog import AirportCatalog


_CATALOG = AirportCatalog.load_default()
_CITY_CODE_FIELDS = {
    "departure": (
        "departureCityCode",
        "departureCityTlc",
        "departCityCode",
        "dcity",
    ),
    "arrival": (
        "arrivalCityCode",
        "arrivalCityTlc",
        "arriveCityCode",
        "acity",
    ),
}
_AIRPORT_CODE_FIELDS = {
    "departure": (
        "departureAirportCode",
        "departureAirportTlc",
        "departureAirportIataCode",
    ),
    "arrival": (
        "arrivalAirportCode",
        "arrivalAirportTlc",
        "arrivalAirportIataCode",
    ),
}
_DEPARTURE_DATETIME_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}"
    r"(?:\.\d{1,6})?(?:Z|[+-]\d{2}:\d{2})?\Z"
)


class CtripBatchSearchParseError(ValueError):
    pass


class _CtripScopeEvidenceError(CtripBatchSearchParseError):
    pass


class _CtripFlightOffer(FlightOffer):
    @property
    def display_price(self) -> int | None:
        return self.total_price


def parse_batch_search(
    payload: Mapping[str, Any], query: FlightQuery
) -> list[FlightOffer]:
    inventory = _inventory_from_payload(payload)
    offers: list[FlightOffer] = []
    malformed_items = 0

    for itinerary in inventory:
        try:
            offer = _parse_itinerary(itinerary, query)
        except _CtripScopeEvidenceError:
            raise
        except CtripBatchSearchParseError:
            malformed_items += 1
            continue
        if offer is not None:
            offers.append(offer)

    if inventory and malformed_items == len(inventory):
        raise CtripBatchSearchParseError("batchSearch itinerary schema is invalid")
    return offers


def _inventory_from_payload(payload: Mapping[str, Any]) -> Sequence[Any]:
    data = payload.get("data")
    if not isinstance(data, Mapping):
        raise CtripBatchSearchParseError("batchSearch data is missing")
    inventory = data.get("flightItineraryList")
    if not isinstance(inventory, list):
        raise CtripBatchSearchParseError("batchSearch inventory is missing")
    return inventory


def _parse_itinerary(
    itinerary: Any, query: FlightQuery
) -> FlightOffer | None:
    if not isinstance(itinerary, Mapping):
        raise CtripBatchSearchParseError("batchSearch itinerary is invalid")

    segments = itinerary.get("flightSegments")
    if not isinstance(segments, list) or not segments:
        raise CtripBatchSearchParseError("flight segments are missing")
    first_segment = segments[0]
    if not isinstance(first_segment, Mapping):
        raise CtripBatchSearchParseError("flight segment is invalid")
    flights = first_segment.get("flightList")
    if not isinstance(flights, list) or not flights:
        raise CtripBatchSearchParseError("flight list is missing")
    if not all(isinstance(flight, Mapping) for flight in flights):
        raise CtripBatchSearchParseError("flight list is invalid")

    price = _lowest_economy_adult_price(itinerary.get("priceList"))
    if price is None:
        return None

    first_flight = flights[0]
    last_flight = flights[-1]
    flight_numbers = [
        number.strip()
        for flight in flights
        if isinstance((number := flight.get("flightNo")), str) and number.strip()
    ]
    if not flight_numbers:
        raise CtripBatchSearchParseError("flight number is missing")
    airlines = list(
        dict.fromkeys(
            airline.strip()
            for flight in flights
            if isinstance(
                (airline := flight.get("marketAirlineName")), str
            )
            and airline.strip()
        )
    )
    origin_code, origin_airport_code = _actual_route_evidence(
        first_flight,
        direction="departure",
    )
    destination_code, destination_airport_code = _actual_route_evidence(
        last_flight,
        direction="arrival",
    )
    if (
        query.origin_airport_scope is not None
        and origin_airport_code != query.origin_airport_scope
    ) or (
        query.destination_airport_scope is not None
        and destination_airport_code != query.destination_airport_scope
    ):
        return None
    depart_date = _actual_depart_date(
        first_flight.get("departureDateTime")
    )

    return _CtripFlightOffer(
        data_provider="ctrip",
        seller_name="携程",
        flight_no="/".join(flight_numbers),
        airline="/".join(airlines),
        origin_city=_actual_city_name(origin_code, query.origin_city),
        origin_code=origin_code,
        origin_airport_code=origin_airport_code,
        destination_city=_actual_city_name(
            destination_code,
            query.destination_city,
        ),
        destination_code=destination_code,
        destination_airport_code=destination_airport_code,
        depart_date=depart_date,
        depart_time=_time_value(first_flight.get("departureDateTime")),
        arrive_time=_time_value(last_flight.get("arrivalDateTime")),
        duration_minutes=_duration_minutes(flights),
        stops=len(flights) - 1,
        cabin="Y",
        currency=query.currency,
        base_price=price,
        tax=None,
        baggage_fee=None,
        total_price=price,
        has_baggage=None,
        price_status=PriceStatus.priced,
    )


def _actual_route_evidence(
    flight: Mapping[str, Any],
    *,
    direction: str,
) -> tuple[str, str | None]:
    actual_city_codes: set[str] = set()
    for field in _CITY_CODE_FIELDS[direction]:
        code = _normalized_code(flight.get(field))
        if code is None:
            continue
        location = _CATALOG.resolve_location(code)
        actual_city_codes.add(
            location.provider_code("ctrip")
            if location is not None
            else code
        )

    actual_airport_codes: set[str] = set()
    for field in _AIRPORT_CODE_FIELDS[direction]:
        code = _normalized_code(flight.get(field))
        if code is None:
            continue
        location = _CATALOG.resolve_location(code)
        if location is None or location.airport_iata is None:
            raise _CtripScopeEvidenceError(
                "flight airport code is unknown"
            )
        actual_airport_codes.add(location.airport_iata)
        actual_city_codes.add(location.provider_code("ctrip"))

    if not actual_city_codes:
        raise _CtripScopeEvidenceError(
            f"{direction} route evidence is missing"
        )
    if len(actual_city_codes) != 1 or len(actual_airport_codes) > 1:
        raise _CtripScopeEvidenceError(
            f"{direction} route evidence conflicts"
        )

    actual_airport = (
        next(iter(actual_airport_codes)) if actual_airport_codes else None
    )
    return next(iter(actual_city_codes)), actual_airport


def _normalized_code(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise _CtripScopeEvidenceError("flight route code is invalid")
    code = value.strip().upper()
    if not code:
        return None
    if len(code) != 3 or not code.isascii() or not code.isalpha():
        raise _CtripScopeEvidenceError("flight route code is invalid")
    return code


def _actual_city_name(code: str, fallback: str) -> str:
    location = _CATALOG.resolve_location(code)
    return location.city_name if location is not None else fallback


def _actual_depart_date(value: Any) -> str:
    if (
        not isinstance(value, str)
        or _DEPARTURE_DATETIME_PATTERN.fullmatch(value) is None
    ):
        raise _CtripScopeEvidenceError("departure date is missing")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _CtripScopeEvidenceError(
            "departure date is invalid"
        ) from exc
    return parsed.date().isoformat()


def _lowest_economy_adult_price(price_list: Any) -> int | None:
    if not isinstance(price_list, list):
        raise CtripBatchSearchParseError("price list is missing")
    prices: list[int] = []
    for price_item in price_list:
        if not isinstance(price_item, Mapping) or price_item.get("cabin") != "Y":
            continue
        adult_price = price_item.get("adultPrice")
        if isinstance(adult_price, bool):
            continue
        try:
            amount = int(adult_price)
        except (TypeError, ValueError):
            continue
        if amount > 0:
            prices.append(amount)
    return min(prices, default=None)


def _duration_minutes(flights: Sequence[Mapping[Any, Any]]) -> int | None:
    durations: list[int] = []
    for flight in flights:
        duration = flight.get("duration")
        if isinstance(duration, bool):
            continue
        try:
            minutes = int(duration)
        except (TypeError, ValueError):
            continue
        if minutes >= 0:
            durations.append(minutes)
    return sum(durations) if len(durations) == len(flights) else None


def _time_value(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    separator = "T" if "T" in value else " "
    parts = value.split(separator, 1)
    return parts[1][:5] if len(parts) == 2 else ""
