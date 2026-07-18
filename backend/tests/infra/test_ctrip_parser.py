from __future__ import annotations

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
    assert offers[0].display_price == 680
    assert offers[0].tax is None
    assert offers[0].baggage_fee is None
    assert offers[0].has_baggage is None
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
    flight["arrivalCityCode"] = "SZX"
    flight["departureDateTime"] = "2026-08-09 08:00:00"

    offer = parse_batch_search(ctrip_payload, query)[0]

    assert offer.origin_code == "CAN"
    assert offer.destination_code == "SZX"
    assert offer.depart_date == "2026-08-09"
