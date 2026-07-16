from datetime import date

import pytest

from backend.application.services.flight_query import (
    FlightQueryValidationError,
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
    with pytest.raises(FlightQueryValidationError, match="无法识别"):
        build_flight_query("不存在的城市", "上海", "2099-08-01", today=date(2026, 7, 16))
