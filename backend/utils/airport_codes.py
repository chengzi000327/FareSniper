from __future__ import annotations

CITY_TO_AIRPORT: dict[str, str] = {
    "北京": "BJS",
    "上海": "SHA",
    "广州": "CAN",
    "深圳": "SZX",
    "杭州": "HGH",
    "成都": "CTU",
    "重庆": "CKG",
    "三亚": "SYX",
    "昆明": "KMG",
    "厦门": "XMN",
    "西安": "XIY",
    "南京": "NKG",
    "武汉": "WUH",
    "长沙": "CSX",
}

AIRPORT_TO_CITY: dict[str, str] = {code: city for city, code in CITY_TO_AIRPORT.items()}


def code_to_city(code: str) -> str:
    return AIRPORT_TO_CITY.get(code, code)


def city_to_code(city: str) -> str:
    return CITY_TO_AIRPORT.get(city, city)
