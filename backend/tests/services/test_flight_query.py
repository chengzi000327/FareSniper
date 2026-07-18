from datetime import date

import pytest

from backend.application.services.flight_query import (
    FlightQueryError,
    FlightQueryValidationError,
    RouteRegion,
    build_flight_query,
)


def test_code_normalizes_to_chinese_city():
    query = build_flight_query("BJS", "SHA", "2099-08-01", today=date(2026, 7, 16))
    assert (query.origin_city, query.destination_city) == ("北京", "上海")
    assert query.is_mainland_domestic is True


def test_hong_kong_is_not_mainland_domestic():
    query = build_flight_query("上海", "香港", "2099-08-01", today=date(2026, 7, 16))
    assert query.destination_code == "HKG"
    assert query.is_mainland_domestic is False


def test_serpapi_ids_are_separate_from_ctrip_city_code():
    query = build_flight_query("上海", "新加坡", "2099-08-01", today=date(2026, 7, 16))
    assert query.origin_code == "SHA"
    assert query.origin_airport_ids == ["PVG", "SHA"]
    assert query.destination_airport_ids == ["SIN"]


@pytest.mark.parametrize("value", ["2026-07-15", "2026-07-16", "not-a-date"])
def test_rejects_non_future_or_invalid_date(value):
    with pytest.raises(FlightQueryValidationError):
        build_flight_query("北京", "上海", value, today=date(2026, 7, 16))


def test_unknown_city_is_not_guessed():
    with pytest.raises(FlightQueryError, match="无法识别城市或机场"):
        build_flight_query("不存在的城市", "上海", "2099-08-01", today=date(2026, 7, 16))


def test_build_query_supports_non_hot_mainland_city():
    query = build_flight_query(
        "阿勒泰", "黔江", "2026-08-08", today=date(2026, 7, 19)
    )

    assert query.origin.city_name == "阿勒泰"
    assert query.destination.airport_iata == "JIQ"
    assert query.origin_code == "AAT"
    assert query.destination_code == "JIQ"
    assert query.route_region is RouteRegion.mainland_domestic


def test_hong_kong_macau_taiwan_are_cross_border():
    shenzhen_hong_kong = build_flight_query(
        "深圳", "香港", "2026-08-08", today=date(2026, 7, 19)
    )
    macau_taipei = build_flight_query(
        "澳门", "台北", "2026-08-08", today=date(2026, 7, 19)
    )

    assert shenzhen_hong_kong.route_region is RouteRegion.cross_border
    assert macau_taipei.route_region is RouteRegion.cross_border


def test_international_route_is_classified_separately():
    query = build_flight_query(
        "上海", "新加坡", "2026-08-08", today=date(2026, 7, 19)
    )

    assert query.route_region is RouteRegion.international


def test_explicit_airport_keeps_single_airport_constraint():
    query = build_flight_query(
        "北京大兴机场", "上海", "2026-08-08", today=date(2026, 7, 19)
    )

    assert query.origin.city_name == "北京"
    assert query.origin.airport_iata == "PKX"
    assert query.origin_airport_ids == ["PKX"]
    assert query.origin_code == "BJS"
