from __future__ import annotations

from langchain_core.tools import tool

from backend.application.services.flight_query import (
    FlightQueryValidationError,
    build_flight_query,
)
from backend.application.services.flight_search_aggregator import (
    FlightSearchAggregator,
)
from backend.application.services.search_events import emit_search_event
from backend.config import settings
from backend.infrastructure.flight_data.providers.factory import (
    build_flight_providers,
)


@tool
async def search_flights(
    origin: str, destination: str, depart_date: str
) -> dict:
    """查询指定出发地、目的地和日期的真实航班报价。"""
    try:
        query = build_flight_query(origin, destination, depart_date)
    except FlightQueryValidationError as exc:
        message = str(exc)
        emit_search_event("validation_error", {"message": message})
        return {
            "deals": [],
            "source": "validation_error",
            "provider_statuses": {},
            "validation_error": message,
        }

    aggregator = FlightSearchAggregator(
        build_flight_providers(),
        timeout_seconds=settings.flight_provider_timeout_seconds,
    )
    return await aggregator.collect(query)
