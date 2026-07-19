from __future__ import annotations

from collections.abc import Iterable
from datetime import date, datetime
from math import asin, cos, radians, sin, sqrt
from zoneinfo import ZoneInfo

from backend.application.services.airport_catalog import AirportCatalog


_CATALOG = AirportCatalog.load_default()
_MAINLAND_DEVELOPMENT_FUND = 50
_FUEL_POLICIES = (
    # Ticket-sale date, <= 800 km, > 800 km.
    (date(2026, 7, 5), 50, 100),
    (date(2026, 6, 5), 80, 150),
    (date(2026, 5, 16), 90, 170),
    (date(2026, 4, 5), 60, 120),
)


def mainland_domestic_tax(
    segments: Iterable[tuple[str | None, str | None]],
    *,
    as_of: date | None = None,
) -> int | None:
    """Estimate mandatory adult fees for mainland domestic segments."""

    policy = _fuel_policy(
        as_of or datetime.now(ZoneInfo("Asia/Shanghai")).date()
    )
    if policy is None:
        return None

    segment_list = list(segments)
    if not segment_list:
        return None

    total = 0
    short_fuel, long_fuel = policy
    for origin_code, destination_code in segment_list:
        distance = _distance_km(origin_code, destination_code)
        if distance is None:
            return None
        total += _MAINLAND_DEVELOPMENT_FUND
        total += short_fuel if distance <= 800 else long_fuel
    return total


def _fuel_policy(as_of: date) -> tuple[int, int] | None:
    for effective_from, short_fuel, long_fuel in _FUEL_POLICIES:
        if as_of >= effective_from:
            return short_fuel, long_fuel
    return None


def _distance_km(
    origin_code: str | None,
    destination_code: str | None,
) -> float | None:
    if not origin_code or not destination_code:
        return None
    origin_location = _CATALOG.resolve_location(origin_code)
    destination_location = _CATALOG.resolve_location(destination_code)
    origin = _CATALOG.resolve_airport(origin_code)
    destination = _CATALOG.resolve_airport(destination_code)
    if (
        origin_location is None
        or destination_location is None
        or origin_location.region_group != "mainland"
        or destination_location.region_group != "mainland"
        or origin is None
        or destination is None
        or origin.latitude is None
        or origin.longitude is None
        or destination.latitude is None
        or destination.longitude is None
    ):
        return None

    lat1 = radians(origin.latitude)
    lat2 = radians(destination.latitude)
    delta_lat = lat2 - lat1
    delta_lon = radians(destination.longitude - origin.longitude)
    haversine = (
        sin(delta_lat / 2) ** 2
        + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    )
    return 2 * 6371.0088 * asin(sqrt(haversine))
