"""热门航线常量的单一来源（single source of truth）。

推荐瀑布流与爬虫调度（multi_platform）共用同一份北京出发热门 OD 对，
避免两边各维护一份导致漂移。城市中文名 / 路线标签也集中在此。
"""
from __future__ import annotations

from types import MappingProxyType

from backend.application.services.airport_catalog import AirportCatalog
from backend.utils.airport_codes import code_to_city

# 北京出发热门目的地（国内高频 OD 对）。
# 从最初的 5 条扩到 14 条，给探索页瀑布流足够的卡片池做无限滚动。
HOT_ROUTES: list[tuple[str, str]] = [
    ("BJS", "SHA"),  # 北京→上海
    ("BJS", "SYX"),  # 北京→三亚
    ("BJS", "CTU"),  # 北京→成都
    ("BJS", "CAN"),  # 北京→广州
    ("BJS", "XMN"),  # 北京→厦门
    ("BJS", "CKG"),  # 北京→重庆
    ("BJS", "SZX"),  # 北京→深圳
    ("BJS", "KMG"),  # 北京→昆明
    ("BJS", "XIY"),  # 北京→西安
    ("BJS", "HGH"),  # 北京→杭州
    ("BJS", "WUH"),  # 北京→武汉
    ("BJS", "URC"),  # 北京→乌鲁木齐
    ("BJS", "HRB"),  # 北京→哈尔滨
    ("BJS", "TAO"),  # 北京→青岛
    ("BJS", "DLC"),  # 北京→大连
]

_AIRPORT_CATALOG = AirportCatalog.load_default()


def _build_discovery_routes() -> list[tuple[str, str]]:
    """热门报价航线优先，其余可售城市补成可查询的探索池。"""
    routes = list(HOT_ROUTES)
    seen = set(routes)
    for city in _AIRPORT_CATALOG.cities:
        destination = city.provider_codes.get("ctrip")
        route = ("BJS", destination) if destination else None
        if (
            route is None
            or destination == "BJS"
            or route in seen
            or not any(
                airport.bookable and airport.commercial_passenger
                for airport in city.airports
            )
        ):
            continue
        routes.append(route)
        seen.add(route)
    return routes


# 探索 Feed 的完整目的地池。只有 HOT_ROUTES 会触发快照查询，其余路线
# 只作为真实查票入口，不在没有库存证据时展示价格。
DISCOVERY_ROUTES = _build_discovery_routes()

CITY_NAMES = MappingProxyType(
    {
        code: city.name
        for city in _AIRPORT_CATALOG.cities
        for code in city.provider_codes.values()
    }
)


def route_city_name(code: str) -> str:
    return code_to_city(code)

# 路线运营标签（卡片上展示的氛围标签）
ROUTE_TAGS: dict[tuple[str, str], list[str]] = {
    ("BJS", "SHA"): ["商务出行", "高铁竞争"],
    ("BJS", "SYX"): ["海岛度假", "阳光沙滩"],
    ("BJS", "CTU"): ["美食天堂", "熊猫故乡"],
    ("BJS", "CAN"): ["湾区热线", "广府文化"],
    ("BJS", "XMN"): ["鼓浪屿", "小清新"],
    ("BJS", "CKG"): ["山城火锅", "8D 魔幻"],
    ("BJS", "SZX"): ["创新之都", "湾区前沿"],
    ("BJS", "KMG"): ["四季如春", "彩云之南"],
    ("BJS", "XIY"): ["千年古都", "兵马俑"],
    ("BJS", "HGH"): ["西湖烟雨", "江南水乡"],
    ("BJS", "WUH"): ["江城樱花", "九省通衢"],
    ("BJS", "URC"): ["大美新疆", "丝路风情"],
    ("BJS", "HRB"): ["冰雪之城", "欧陆风情"],
    ("BJS", "TAO"): ["红瓦绿树", "啤酒海风"],
    ("BJS", "DLC"): ["浪漫海滨", "北方明珠"],
}
