from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.application.services.airport_catalog import AirportCatalog


CATALOG_PATH = Path(__file__).parents[2] / "data" / "china_airports.json"


def test_default_catalog_covers_all_regions() -> None:
    catalog = AirportCatalog.load_default()

    assert catalog.metadata.mainland_transport_airports >= 270
    assert {"mainland", "hong_kong", "macau", "taiwan"} <= {
        city.region_group for city in catalog.cities
    }
    mainland_airports = [
        airport
        for city in catalog.cities
        for airport in city.airports
        if airport.region_group == "mainland"
    ]
    assert len(mainland_airports) == catalog.metadata.mainland_transport_airports
    assert catalog.metadata.excluded_airports == {}
    reconciliation = catalog.metadata.regional_reconciliation
    assert reconciliation["source_candidate_airports"] == {
        "hong_kong": 1,
        "macau": 1,
        "taiwan": 19,
    }
    assert reconciliation["included_airports"] == {
        "hong_kong": 1,
        "macau": 1,
        "taiwan": 16,
    }
    assert set(reconciliation["excluded_airports"]) == {"DSX", "HCN", "HSZ"}


def test_multi_airport_and_specific_airport_resolution() -> None:
    catalog = AirportCatalog.load_default()

    assert catalog.resolve_location("北京").provider_code("ctrip") == "BJS"
    assert catalog.resolve_location("北京大兴机场").airport_iata == "PKX"
    assert catalog.resolve_location("PVG").city_name == "上海"
    assert catalog.resolve_location("香港").provider_code("ctrip") == "HKG"
    assert catalog.resolve_location("台北桃园机场").airport_iata == "TPE"


def test_plain_city_wins_normalized_name_collision_but_airport_input_stays_specific(
) -> None:
    catalog = AirportCatalog.load_default()

    assert catalog.resolve_location("义乌").city_name == "义乌"
    assert catalog.resolve_location("义乌").airport_iata is None
    assert catalog.resolve_location("义乌机场").airport_iata == "YIW"
    assert catalog.resolve_location("YIW").airport_iata == "YIW"
    assert catalog.resolve_location("ZSYW").airport_icao == "ZSYW"

    assert catalog.resolve_city("SHA").name == "上海"
    assert catalog.resolve_airport("SHA").iata == "SHA"
    assert catalog.resolve_location("上海").airport_iata is None
    assert catalog.resolve_location("SHA").airport_iata == "SHA"


def test_resolution_normalizes_only_documented_variants() -> None:
    catalog = AirportCatalog.load_default()

    assert catalog.resolve_location("  北京市 ").city_name == "北京"
    assert catalog.resolve_location("pkx").airport_iata == "PKX"
    assert catalog.resolve_location("北京不存在机场") is None
    assert catalog.resolve_location("北景") is None


def test_no_duplicate_codes_or_non_bookable_airports() -> None:
    catalog = AirportCatalog.load_default()
    iata = [airport.iata for city in catalog.cities for airport in city.airports]
    icao = [airport.icao for city in catalog.cities for airport in city.airports]

    assert len(iata) == len(set(iata))
    assert len(icao) == len(set(icao))
    assert all(airport.bookable for city in catalog.cities for airport in city.airports)


def test_city_and_airport_resolvers_keep_their_scope() -> None:
    catalog = AirportCatalog.load_default()

    assert catalog.resolve_city("BJS").name == "北京"
    assert catalog.resolve_city("PEK") is None
    assert catalog.resolve_airport("北京首都国际机场").iata == "PEK"
    assert catalog.resolve_airport("BJS") is None
    assert catalog.code_to_city("rctp") == "台北"
    assert catalog.city_to_provider_code("beijing", "serpapi") == "BJS"


def test_catalog_rejects_cross_city_city_airport_index_ambiguity() -> None:
    payload = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    beijing = next(city for city in payload["cities"] if city["city_id"] == "beijing")
    beijing["aliases"].append("ZSYW")

    with pytest.raises(ValueError, match="cross-index ambiguity"):
        AirportCatalog(payload)
