from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from backend.application.services.airport_catalog import AirportCatalog


@dataclass(frozen=True)
class AirportRef:
    city: str
    code: str
    airport_ids: tuple[str, ...]
    mainland_china: bool


_CATALOG = AirportCatalog.load_default()
_CHINA_REFS = tuple(
    AirportRef(
        city=city.name,
        code=city.provider_codes["ctrip"],
        airport_ids=tuple(airport.iata for airport in city.airports),
        mainland_china=city.region_group == "mainland",
    )
    for city in _CATALOG.cities
)
_INTERNATIONAL_REFS = (
    AirportRef("东京", "TYO", ("HND", "NRT"), False),
    AirportRef("大阪", "OSA", ("KIX",), False),
    AirportRef("首尔", "SEL", ("ICN", "GMP"), False),
    AirportRef("新加坡", "SIN", ("SIN",), False),
    AirportRef("曼谷", "BKK", ("BKK",), False),
    AirportRef("吉隆坡", "KUL", ("KUL",), False),
    AirportRef("伦敦", "LON", ("LHR", "LGW"), False),
    AirportRef("巴黎", "PAR", ("CDG", "ORY"), False),
    AirportRef("纽约", "NYC", ("JFK", "EWR", "LGA"), False),
    AirportRef("洛杉矶", "LAX", ("LAX",), False),
    AirportRef("悉尼", "SYD", ("SYD",), False),
)
_AIRPORT_CATALOG = _CHINA_REFS + _INTERNATIONAL_REFS
_AIRPORT_BY_CITY = MappingProxyType({ref.city: ref for ref in _AIRPORT_CATALOG})
_AIRPORT_BY_CODE = MappingProxyType({ref.code: ref for ref in _AIRPORT_CATALOG})
_INTERNATIONAL_BY_AIRPORT = MappingProxyType(
    {
        airport_id: ref
        for ref in _INTERNATIONAL_REFS
        for airport_id in ref.airport_ids
    }
)

CITY_TO_AIRPORT = MappingProxyType(
    {ref.city: ref.code for ref in _AIRPORT_CATALOG}
)
AIRPORT_TO_CITY = MappingProxyType(
    {
        code: ref.city
        for ref in _AIRPORT_CATALOG
        for code in (ref.code, *ref.airport_ids)
    }
)


def resolve_airport(value: str) -> AirportRef | None:
    ref = _AIRPORT_BY_CITY.get(value)
    if ref is not None:
        return ref

    location = _CATALOG.resolve_location(value)
    if location is not None:
        city_ref = _AIRPORT_BY_CITY[location.city_name]
        if location.airport_iata:
            return AirportRef(
                city=city_ref.city,
                code=city_ref.code,
                airport_ids=(location.airport_iata,),
                mainland_china=city_ref.mainland_china,
            )
        return city_ref
    return _AIRPORT_BY_CODE.get(value.upper()) or _INTERNATIONAL_BY_AIRPORT.get(
        value.upper()
    )


def code_to_city(code: str) -> str:
    city = _CATALOG.code_to_city(code)
    if city != code:
        return city
    ref = _AIRPORT_BY_CODE.get(code.upper()) or _INTERNATIONAL_BY_AIRPORT.get(
        code.upper()
    )
    return ref.city if ref else code


def city_to_code(city: str) -> str:
    ref = resolve_airport(city)
    return ref.code if ref else city
