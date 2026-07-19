from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from backend.application.contracts.flight_provider import FlightQuery, PriceStatus
from backend.infrastructure.flight_data.ctrip_parser import (
    CtripBatchSearchParseError,
    parse_batch_search,
)


@pytest.fixture
def ctrip_payload() -> dict:
    path = Path(__file__).parents[1] / "fixtures/providers/ctrip_batch_search.json"
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def query() -> FlightQuery:
    return FlightQuery(
        origin_city="北京",
        origin_code="BJS",
        origin_airport_ids=["PEK", "PKX"],
        destination_city="上海",
        destination_code="SHA",
        destination_airport_ids=["SHA", "PVG"],
        depart_date="2026-08-08",
        is_mainland_domestic=True,
    )


def test_parser_keeps_only_real_ctrip_fields(ctrip_payload, query):
    offers = parse_batch_search(ctrip_payload, query)

    assert offers[0].seller_name == "携程"
    assert offers[0].base_price == 680
    assert offers[0].tax == 150
    assert offers[0].tax_source == "regulatory_estimate"
    assert offers[0].baggage_fee == 0
    assert offers[0].baggage_allowance == "20KG"
    assert offers[0].has_baggage is True
    assert offers[0].display_price == 830
    assert offers[0].price_status is PriceStatus.priced
    assert {offer.seller_name for offer in offers} == {"携程"}


def test_parser_rejects_missing_batch_search_inventory(query):
    with pytest.raises(CtripBatchSearchParseError):
        parse_batch_search({"code": 0, "data": {}}, query)


def test_parser_preserves_payload_scope_instead_of_rewriting_from_query(
    ctrip_payload,
    query,
):
    flight = ctrip_payload["data"]["flightItineraryList"][0][
        "flightSegments"
    ][0]["flightList"][0]
    flight["departureCityCode"] = "CAN"
    flight["departureAirportCode"] = "CAN"
    flight["arrivalCityCode"] = "SZX"
    flight["arrivalAirportCode"] = "SZX"
    flight["departureDateTime"] = "2026-08-09 08:00:00"

    offer = parse_batch_search(ctrip_payload, query)[0]

    assert offer.origin_code == "CAN"
    assert offer.destination_code == "SZX"
    assert offer.depart_date == "2026-08-09"


def test_parser_filters_inventory_to_explicit_airport_scope(
    ctrip_payload,
):
    query = FlightQuery(
        origin_city="北京",
        origin_code="BJS",
        origin_airport_ids=["PKX"],
        origin_airport_scope="PKX",
        destination_city="上海",
        destination_code="SHA",
        destination_airport_ids=["SHA"],
        destination_airport_scope="SHA",
        depart_date="2026-08-08",
        is_mainland_domestic=True,
    )
    pek_itinerary = ctrip_payload["data"]["flightItineraryList"][0]
    pkx_itinerary = copy.deepcopy(pek_itinerary)
    pkx_flight = pkx_itinerary["flightSegments"][0]["flightList"][0]
    pkx_flight["flightNo"] = "CZ3001"
    pkx_flight["departureAirportCode"] = "PKX"
    ctrip_payload["data"]["flightItineraryList"] = [
        pek_itinerary,
        pkx_itinerary,
    ]

    offers = parse_batch_search(ctrip_payload, query)

    assert [offer.flight_no for offer in offers] == ["CZ3001"]
    assert offers[0].origin_code == "BJS"
    assert offers[0].origin_airport_code == "PKX"
    assert offers[0].destination_code == "SHA"
    assert offers[0].destination_airport_code == "SHA"


@pytest.mark.parametrize("missing_direction", ["departure", "arrival"])
def test_parser_requires_real_route_evidence_per_direction(
    ctrip_payload,
    query,
    missing_direction,
):
    flight = ctrip_payload["data"]["flightItineraryList"][0][
        "flightSegments"
    ][0]["flightList"][0]
    fields = {
        "departure": (
            "departureCityCode",
            "departureCityTlc",
            "departCityCode",
            "dcity",
            "departureAirportCode",
            "departureAirportTlc",
            "departureAirportIataCode",
        ),
        "arrival": (
            "arrivalCityCode",
            "arrivalCityTlc",
            "arriveCityCode",
            "acity",
            "arrivalAirportCode",
            "arrivalAirportTlc",
            "arrivalAirportIataCode",
        ),
    }
    flight["departureCityCode"] = "BJS"
    flight["arrivalCityCode"] = "SHA"
    for field in fields[missing_direction]:
        flight.pop(field, None)

    with pytest.raises(CtripBatchSearchParseError):
        parse_batch_search(ctrip_payload, query)


@pytest.mark.parametrize("conflicting_direction", ["departure", "arrival"])
def test_parser_rejects_conflicting_normalized_route_codes(
    ctrip_payload,
    query,
    conflicting_direction,
):
    flight = ctrip_payload["data"]["flightItineraryList"][0][
        "flightSegments"
    ][0]["flightList"][0]
    flight.update(
        {
            "departureCityCode": "BJS",
            "departureAirportCode": "PEK",
            "arrivalCityCode": "SHA",
            "arrivalAirportCode": "PVG",
        }
    )
    if conflicting_direction == "departure":
        flight["departureAirportTlc"] = "CAN"
    else:
        flight["arrivalAirportTlc"] = "SZX"

    with pytest.raises(CtripBatchSearchParseError):
        parse_batch_search(ctrip_payload, query)


def test_any_conflicting_itinerary_rejects_entire_batch(
    ctrip_payload,
    query,
):
    valid = ctrip_payload["data"]["flightItineraryList"][0]
    conflicting = copy.deepcopy(valid)
    conflicting["flightSegments"][0]["flightList"][0][
        "departureAirportTlc"
    ] = "CAN"
    ctrip_payload["data"]["flightItineraryList"] = [valid, conflicting]

    with pytest.raises(CtripBatchSearchParseError):
        parse_batch_search(ctrip_payload, query)


def test_parser_accepts_multiple_consistent_city_and_airport_codes(
    ctrip_payload,
    query,
):
    flight = ctrip_payload["data"]["flightItineraryList"][0][
        "flightSegments"
    ][0]["flightList"][0]
    flight.update(
        {
            "departureCityCode": "BJS",
            "departureAirportCode": "PEK",
            "departureAirportTlc": "PEK",
            "arrivalCityCode": "SHA",
            "arrivalAirportCode": "PVG",
            "arrivalAirportTlc": "PVG",
        }
    )

    offer = parse_batch_search(ctrip_payload, query)[0]

    assert offer.origin_code == "BJS"
    assert offer.destination_code == "SHA"


@pytest.mark.parametrize(
    ("value", "expected_date"),
    [
        ("2026-08-08 08:00:00", "2026-08-08"),
        ("2026-08-08T08:00:00Z", "2026-08-08"),
        ("2026-08-08T08:00:00+08:00", "2026-08-08"),
    ],
)
def test_parser_accepts_complete_iso_departure_datetime(
    ctrip_payload,
    query,
    value,
    expected_date,
):
    flight = ctrip_payload["data"]["flightItineraryList"][0][
        "flightSegments"
    ][0]["flightList"][0]
    flight.update(
        {
            "departureCityCode": "BJS",
            "arrivalCityCode": "SHA",
            "departureDateTime": value,
        }
    )

    assert parse_batch_search(ctrip_payload, query)[0].depart_date == expected_date


@pytest.mark.parametrize(
    "value",
    [
        "2026-08-08",
        "2026-08-08 25:00:00",
        "2026-08-08T08:00:00Z trailing",
        "2026-08-08T08:00:00+99:00",
    ],
)
def test_parser_rejects_invalid_or_trailing_departure_datetime(
    ctrip_payload,
    query,
    value,
):
    flight = ctrip_payload["data"]["flightItineraryList"][0][
        "flightSegments"
    ][0]["flightList"][0]
    flight.update(
        {
            "departureCityCode": "BJS",
            "arrivalCityCode": "SHA",
            "departureDateTime": value,
        }
    )

    with pytest.raises(CtripBatchSearchParseError):
        parse_batch_search(ctrip_payload, query)
