import importlib
from pathlib import Path

from backend.utils.airport_codes import (
    CITY_TO_AIRPORT,
    code_to_city,
    city_to_code,
    resolve_airport,
)
from backend.application.services import recommendation_service


class TestCodeToCity:
    def test_all_known_codes(self) -> None:
        expected = {
            "BJS": "北京", "SHA": "上海", "CAN": "广州", "SZX": "深圳",
            "HGH": "杭州", "CTU": "成都", "CKG": "重庆", "SYX": "三亚",
            "KMG": "昆明", "XMN": "厦门", "XIY": "西安", "NKG": "南京",
            "WUH": "武汉", "CSX": "长沙",
        }
        for code, city in expected.items():
            assert code_to_city(code) == city

    def test_unknown_code_returns_itself(self) -> None:
        assert code_to_city("ZZZ") == "ZZZ"


class TestCityToCode:
    def test_all_known_cities(self) -> None:
        for city, code in CITY_TO_AIRPORT.items():
            assert city_to_code(city) == code

    def test_unknown_city_returns_itself(self) -> None:
        assert city_to_code("火星") == "火星"


def test_specific_airport_code_preserves_airport_constraint() -> None:
    assert resolve_airport("SHA").airport_ids == ("SHA",)
    assert resolve_airport("上海").airport_ids == ("PVG", "SHA")


def test_flights_monitor_resolves_catalog_city_and_airport_alias(monkeypatch) -> None:
    monitor_dir = Path(__file__).parents[1] / "third_party" / "flights_monitor"
    monkeypatch.syspath_prepend(str(monitor_dir))
    shared = importlib.import_module("shared")

    assert shared.resolve_city("阿勒泰") == ("AAT", "阿勒泰")
    assert shared.resolve_city("北京大兴机场") == ("BJS", "北京")


def test_recommendation_route_labels_use_catalog() -> None:
    card = recommendation_service._build_card("AAT", "JIQ", None, None, 0)

    assert card.title == "阿勒泰→黔江"
