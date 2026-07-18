from __future__ import annotations

from backend.application.services.airport_catalog import AirportCatalog


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


def test_multi_airport_and_specific_airport_resolution() -> None:
    catalog = AirportCatalog.load_default()

    assert catalog.resolve_location("北京").provider_code("ctrip") == "BJS"
    assert catalog.resolve_location("北京大兴机场").airport_iata == "PKX"
    assert catalog.resolve_location("PVG").city_name == "上海"
    assert catalog.resolve_location("香港").provider_code("ctrip") == "HKG"
    assert catalog.resolve_location("台北桃园机场").airport_iata == "TPE"


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
