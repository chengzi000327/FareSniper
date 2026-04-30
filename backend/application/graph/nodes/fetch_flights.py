"""Flight search node."""

from __future__ import annotations

import asyncio

from backend.application.contracts.intent import IntentConstraintType, NormalizedIntent
from backend.application.contracts.search import (
    FlightCandidate,
    FlightSearchResult,
    PlatformPrice,
)
from backend.application.graph.state import WorkflowState
from backend.data_sources.mock_flights import get_mock_flights


async def run_flight_search(state: WorkflowState) -> WorkflowState:
    intent: NormalizedIntent = state["intent"]

    raw_flights, _ = await asyncio.gather(
        _fetch(intent),
        asyncio.sleep(0),
    )

    origin_city = intent.origin.city if intent.origin else ""
    dest_city = intent.destination.city if intent.destination else ""
    date = intent.date_window.start_date if intent.date_window else ""

    result = FlightSearchResult(
        candidates=[_to_candidate(f) for f in raw_flights],
        source="mock",
        query_origin=origin_city,
        query_destination=dest_city,
        query_date=date,
    )
    return {**state, "search_result": result}


async def _fetch(intent: NormalizedIntent) -> list[dict]:
    origin = intent.origin.city if intent.origin else ""
    dest = intent.destination.city if intent.destination else ""
    date = intent.date_window.start_date if intent.date_window else ""
    try:
        flights = get_mock_flights(origin, dest, date)
    except Exception:
        flights = []

    direct_only = any(c.type == IntentConstraintType.direct_only for c in intent.constraints)
    if direct_only:
        flights = [f for f in flights if f.get("stops", 0) == 0]
    return flights


def _to_candidate(raw: dict) -> FlightCandidate:
    prices = [
        PlatformPrice(
            platform=p.get("name", p.get("platform", "")),
            price=p["price"],
            url=p.get("url", ""),
            lowest=p.get("lowest", False),
        )
        for p in raw.get("prices", [])
    ]
    lowest = raw.get("lowest_price", raw.get("price", 0))
    return FlightCandidate(
        flight_no=raw.get("flight_no", ""),
        airline=raw.get("airline", ""),
        depart_time=raw.get("depart_time", raw.get("dep_time", "")),
        arrive_time=raw.get("arrive_time", raw.get("arr_time", "")),
        duration=raw.get("duration", ""),
        stops=raw.get("stops", 0),
        depart_date=raw.get("depart_date", ""),
        origin_city=raw.get("origin_city", ""),
        origin_code=raw.get("origin_code", ""),
        destination_city=raw.get("destination_city", ""),
        destination_code=raw.get("destination_code", ""),
        prices=prices,
        price=raw.get("price", lowest),
        lowest_price=lowest,
        history_avg_90d=raw.get("history_avg_90d"),
        history_low_90d=raw.get("history_low_90d"),
        tax=raw.get("tax", 0),
        baggage_fee=raw.get("baggage_fee", 0),
        has_baggage=raw.get("has_baggage", True),
        booking_url=raw.get("booking_url", ""),
        h5_fallback_url=raw.get("h5_fallback_url", ""),
    )
