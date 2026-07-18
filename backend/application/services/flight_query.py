from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from enum import Enum
from types import MappingProxyType
from zoneinfo import ZoneInfo

from backend.application.contracts.flight_provider import (
    FlightQuery as ProviderFlightQuery,
)
from backend.application.services.airport_catalog import (
    AirportCatalog,
    ResolvedLocation,
)
from backend.utils.airport_codes import resolve_airport


class RouteRegion(str, Enum):
    mainland_domestic = "mainland_domestic"
    cross_border = "cross_border"
    international = "international"


class FlightQueryError(ValueError):
    pass


# Keep the established public name used by graph tools and verification scripts.
FlightQueryValidationError = FlightQueryError


class FlightQuery(ProviderFlightQuery):
    origin: ResolvedLocation
    destination: ResolvedLocation
    route_region: RouteRegion


_CATALOG = AirportCatalog.load_default()
_CHINA_REGION_GROUPS = {"mainland", "hong_kong", "macau", "taiwan"}


def _catalog_location(value: str) -> ResolvedLocation | None:
    location = _CATALOG.resolve_location(value)
    if location is None:
        return None
    if location.airport_iata is not None:
        return location

    city = _CATALOG.resolve_city(location.city_name)
    if city is not None and len(city.airports) == 1:
        airport = city.airports[0]
        return replace(
            location,
            airport_iata=airport.iata,
            airport_icao=airport.icao,
        )
    return location


def _international_location(value: str) -> ResolvedLocation | None:
    ref = resolve_airport(value)
    if ref is None or _CATALOG.resolve_location(value) is not None:
        return None
    airport_iata = ref.airport_ids[0] if len(ref.airport_ids) == 1 else None
    codes = MappingProxyType(
        {
            "ctrip": ref.code,
            "flyai": ref.code,
            "serpapi": ref.code,
            "variflight": ref.code,
        }
    )
    return ResolvedLocation(
        city_id=f"international:{ref.code.lower()}",
        city_name=ref.city,
        region_group="international",
        city_codes=codes,
        airport_iata=airport_iata,
    )


def _resolve_location(value: str) -> ResolvedLocation | None:
    return _catalog_location(value) or _international_location(value)


def _airport_ids(location: ResolvedLocation) -> list[str]:
    if location.airport_iata:
        return [location.airport_iata]
    city = _CATALOG.resolve_city(location.city_name)
    if city is not None:
        return [airport.iata for airport in city.airports]
    ref = resolve_airport(location.city_name)
    return list(ref.airport_ids) if ref is not None else []


def _route_region(
    origin: ResolvedLocation, destination: ResolvedLocation
) -> RouteRegion:
    groups = {origin.region_group, destination.region_group}
    if groups == {"mainland"}:
        return RouteRegion.mainland_domestic
    if groups <= _CHINA_REGION_GROUPS:
        return RouteRegion.cross_border
    return RouteRegion.international


def build_flight_query(
    origin: str,
    destination: str,
    depart_date: str,
    *,
    today: date | None = None,
) -> FlightQuery:
    origin_location = _resolve_location(origin)
    destination_location = _resolve_location(destination)
    if origin_location is None or destination_location is None:
        raise FlightQueryError("无法识别城市或机场")

    try:
        parsed = date.fromisoformat(depart_date)
    except ValueError as exc:
        raise FlightQueryError("出发日期必须使用 YYYY-MM-DD") from exc

    current = today or datetime.now(ZoneInfo("Asia/Shanghai")).date()
    if parsed <= current:
        raise FlightQueryError("出发日期必须是未来日期")

    route_region = _route_region(origin_location, destination_location)
    return FlightQuery(
        origin=origin_location,
        destination=destination_location,
        route_region=route_region,
        origin_city=origin_location.city_name,
        origin_code=origin_location.provider_code("ctrip"),
        origin_airport_ids=_airport_ids(origin_location),
        destination_city=destination_location.city_name,
        destination_code=destination_location.provider_code("ctrip"),
        destination_airport_ids=_airport_ids(destination_location),
        depart_date=parsed.isoformat(),
        is_mainland_domestic=route_region is RouteRegion.mainland_domestic,
    )
