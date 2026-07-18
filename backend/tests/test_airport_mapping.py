from backend.utils.airport_codes import (
    CITY_TO_AIRPORT,
    code_to_city,
    city_to_code,
    resolve_airport,
)


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
