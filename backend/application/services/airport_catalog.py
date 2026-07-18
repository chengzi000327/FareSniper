from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping


_WHITESPACE = re.compile(r"\s+")
_AIRPORT_CODE = re.compile(r"[A-Za-z]{3,4}")


def _normalize(value: str) -> str:
    normalized = _WHITESPACE.sub("", value).strip().upper()
    for suffix in ("机场", "市"):
        if normalized.endswith(suffix):
            normalized = normalized[: -len(suffix)]
    return normalized


def _is_explicit_airport_query(value: str) -> bool:
    compact = _WHITESPACE.sub("", value).strip()
    return compact.endswith("机场") or _AIRPORT_CODE.fullmatch(compact) is not None


@dataclass(frozen=True)
class CatalogMetadata:
    catalog_version: str
    generated_at: str
    mainland_transport_airports: int
    mainland_bookable_airports: int
    regional_airports: Mapping[str, int]
    regional_cities: Mapping[str, int]
    excluded_airports: Mapping[str, tuple[str, ...]]
    regional_reconciliation: Mapping[str, Any]
    sources: Mapping[str, Any]


@dataclass(frozen=True)
class Airport:
    name: str
    aliases: tuple[str, ...]
    iata: str
    icao: str | None
    latitude: float | None
    longitude: float | None
    timezone: str | None
    region_group: str
    transport_airport: bool
    commercial_passenger: bool
    status: str
    bookable: bool
    sources: tuple[str, ...]


@dataclass(frozen=True)
class City:
    city_id: str
    name: str
    province: str
    region_group: str
    aliases: tuple[str, ...]
    provider_codes: Mapping[str, str]
    airports: tuple[Airport, ...]


@dataclass(frozen=True)
class ResolvedLocation:
    city_id: str
    city_name: str
    region_group: str
    city_codes: Mapping[str, str]
    airport_iata: str | None = None
    airport_icao: str | None = None

    def provider_code(self, provider: str) -> str:
        return self.city_codes[provider.lower()]


class AirportCatalog:
    def __init__(self, payload: Mapping[str, Any]) -> None:
        metadata = payload["metadata"]
        self.metadata = CatalogMetadata(
            catalog_version=metadata["catalog_version"],
            generated_at=metadata["generated_at"],
            mainland_transport_airports=metadata["mainland_transport_airports"],
            mainland_bookable_airports=metadata["mainland_bookable_airports"],
            regional_airports=MappingProxyType(dict(metadata["regional_airports"])),
            regional_cities=MappingProxyType(dict(metadata["regional_cities"])),
            excluded_airports=MappingProxyType(
                {
                    reason: tuple(names)
                    for reason, names in metadata["excluded_airports"].items()
                }
            ),
            regional_reconciliation=MappingProxyType(
                dict(metadata["regional_reconciliation"])
            ),
            sources=MappingProxyType(dict(metadata["sources"])),
        )
        self.cities = tuple(self._parse_city(city) for city in payload["cities"])
        self._cities_by_id = {city.city_id: city for city in self.cities}
        self._city_index: dict[str, City] = {}
        self._airport_index: dict[str, tuple[City, Airport]] = {}
        for city in self.cities:
            for value in (city.name, *city.aliases, *city.provider_codes.values()):
                self._add_unique(self._city_index, value, city, "city alias")
            for airport in city.airports:
                for value in (
                    airport.name,
                    *airport.aliases,
                    airport.iata,
                    airport.icao,
                ):
                    if value:
                        self._add_unique(
                            self._airport_index,
                            value,
                            (city, airport),
                            "airport alias",
                        )
        for key in self._city_index.keys() & self._airport_index.keys():
            city = self._city_index[key]
            airport_city, _ = self._airport_index[key]
            if city.city_id != airport_city.city_id:
                raise ValueError(f"cross-index ambiguity across cities: {key}")

    @staticmethod
    def _add_unique(
        index: dict[str, Any], value: str, target: Any, description: str
    ) -> None:
        key = _normalize(value)
        existing = index.get(key)
        if existing is not None and existing != target:
            raise ValueError(f"ambiguous {description}: {value}")
        index[key] = target

    @staticmethod
    def _parse_city(payload: Mapping[str, Any]) -> City:
        airports = tuple(
            Airport(
                name=airport["name"],
                aliases=tuple(airport.get("aliases", [])),
                iata=airport["iata"],
                icao=airport.get("icao"),
                latitude=airport.get("latitude"),
                longitude=airport.get("longitude"),
                timezone=airport.get("timezone"),
                region_group=airport["region_group"],
                transport_airport=airport["transport_airport"],
                commercial_passenger=airport["commercial_passenger"],
                status=airport["status"],
                bookable=airport["bookable"],
                sources=tuple(airport["sources"]),
            )
            for airport in payload["airports"]
        )
        return City(
            city_id=payload["city_id"],
            name=payload["name"],
            province=payload["province"],
            region_group=payload["region_group"],
            aliases=tuple(payload.get("aliases", [])),
            provider_codes=MappingProxyType(dict(payload["provider_codes"])),
            airports=airports,
        )

    @classmethod
    def load_default(cls) -> AirportCatalog:
        path = Path(__file__).resolve().parents[2] / "data" / "china_airports.json"
        return cls(json.loads(path.read_text(encoding="utf-8")))

    def resolve_city(self, text: str) -> City | None:
        return self._city_index.get(_normalize(text))

    def resolve_airport(self, text: str) -> Airport | None:
        match = self._airport_index.get(_normalize(text))
        return match[1] if match else None

    def resolve_location(self, text: str) -> ResolvedLocation | None:
        key = _normalize(text)
        city = self._city_index.get(key)
        airport_match = self._airport_index.get(key)
        if airport_match and (_is_explicit_airport_query(text) or city is None):
            airport_city, airport = airport_match
            return self._resolved(airport_city, airport)
        return self._resolved(city) if city else None

    def city_to_provider_code(self, city_id: str, provider: str) -> str:
        return self._cities_by_id[city_id].provider_codes[provider.lower()]

    def code_to_city(self, code: str) -> str:
        location = self.resolve_location(code)
        return location.city_name if location else code

    @staticmethod
    def _resolved(city: City, airport: Airport | None = None) -> ResolvedLocation:
        return ResolvedLocation(
            city_id=city.city_id,
            city_name=city.name,
            region_group=city.region_group,
            city_codes=city.provider_codes,
            airport_iata=airport.iata if airport else None,
            airport_icao=airport.icao if airport else None,
        )


@cache
def _default_catalog() -> AirportCatalog:
    return AirportCatalog.load_default()


def resolve_location(text: str) -> ResolvedLocation | None:
    return _default_catalog().resolve_location(text)


def city_to_provider_code(city_id: str, provider: str) -> str:
    return _default_catalog().city_to_provider_code(city_id, provider)


def code_to_city(code: str) -> str:
    return _default_catalog().code_to_city(code)
