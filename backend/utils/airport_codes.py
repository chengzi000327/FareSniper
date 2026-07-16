from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class AirportRef:
    city: str
    code: str
    airport_ids: tuple[str, ...]
    mainland_china: bool


_AIRPORT_CATALOG = (
    AirportRef("北京", "BJS", ("PEK", "PKX"), True),
    AirportRef("上海", "SHA", ("PVG", "SHA"), True),
    AirportRef("广州", "CAN", ("CAN",), True),
    AirportRef("深圳", "SZX", ("SZX",), True),
    AirportRef("杭州", "HGH", ("HGH",), True),
    AirportRef("成都", "CTU", ("CTU",), True),
    AirportRef("重庆", "CKG", ("CKG",), True),
    AirportRef("三亚", "SYX", ("SYX",), True),
    AirportRef("昆明", "KMG", ("KMG",), True),
    AirportRef("厦门", "XMN", ("XMN",), True),
    AirportRef("西安", "XIY", ("XIY",), True),
    AirportRef("南京", "NKG", ("NKG",), True),
    AirportRef("武汉", "WUH", ("WUH",), True),
    AirportRef("长沙", "CSX", ("CSX",), True),
    AirportRef("香港", "HKG", ("HKG",), False),
    AirportRef("澳门", "MFM", ("MFM",), False),
    AirportRef("台北", "TPE", ("TPE",), False),
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
    AirportRef("乌鲁木齐", "URC", ("URC",), True),
    AirportRef("哈尔滨", "HRB", ("HRB",), True),
    AirportRef("青岛", "TAO", ("TAO",), True),
    AirportRef("大连", "DLC", ("DLC",), True),
)

_AIRPORT_BY_CITY = MappingProxyType({ref.city: ref for ref in _AIRPORT_CATALOG})
_AIRPORT_BY_CODE = MappingProxyType({ref.code: ref for ref in _AIRPORT_CATALOG})

CITY_TO_AIRPORT = MappingProxyType(
    {ref.city: ref.code for ref in _AIRPORT_CATALOG}
)
AIRPORT_TO_CITY = MappingProxyType(
    {ref.code: ref.city for ref in _AIRPORT_CATALOG}
)


def resolve_airport(value: str) -> AirportRef | None:
    return _AIRPORT_BY_CITY.get(value) or _AIRPORT_BY_CODE.get(value)


def code_to_city(code: str) -> str:
    return AIRPORT_TO_CITY.get(code, code)


def city_to_code(city: str) -> str:
    return CITY_TO_AIRPORT.get(city, city)
