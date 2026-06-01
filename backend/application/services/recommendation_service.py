from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

from backend.application.contracts.recommendations import RecCard, RecommendationsResponseDto
from backend.infrastructure.db.base import get_session
from backend.infrastructure.db.flight_snapshot_repo import read_deals
from backend.infrastructure.redis.session_store import _redis
from backend.memory.long_term import LongTermMemory

# 北京出发热门 OD 对（与 scheduler 保持一致）
_HOT_ROUTES: list[tuple[str, str]] = [
    ("BJS", "SHA"),
    ("BJS", "SYX"),
    ("BJS", "CTU"),
    ("BJS", "CAN"),
    ("BJS", "XMN"),
]

_CITY_NAMES: dict[str, str] = {
    "BJS": "北京", "SHA": "上海", "SYX": "三亚", "CTU": "成都",
    "CAN": "广州", "XMN": "厦门", "CKG": "重庆", "SZX": "深圳",
    "NKG": "南京", "HGH": "杭州", "WUH": "武汉", "XIY": "西安",
    "KMG": "昆明", "URC": "乌鲁木齐", "HRB": "哈尔滨",
}

_ROUTE_TAGS: dict[tuple[str, str], list[str]] = {
    ("BJS", "SHA"): ["商务出行", "高铁竞争"],
    ("BJS", "SYX"): ["海岛度假", "阳光沙滩"],
    ("BJS", "CTU"): ["美食天堂", "熊猫故乡"],
    ("BJS", "CAN"): ["湾区热线", "广府文化"],
    ("BJS", "XMN"): ["鼓浪屿", "小清新"],
}

CACHE_TTL = 300   # 5 分钟缓存


async def build_recommendations(user_id: str) -> RecommendationsResponseDto:
    key = f"rec:{user_id}"
    try:
        raw = await _redis().get(key)
        if raw:
            return RecommendationsResponseDto.model_validate_json(raw)
        rsp = await _build_recommendations_uncached(user_id)
        await _redis().setex(key, CACHE_TTL, rsp.model_dump_json())
        return rsp
    except Exception:
        return await _build_recommendations_uncached(user_id)


async def _build_recommendations_uncached(user_id: str) -> RecommendationsResponseDto:
    # 个性化：读 user_preferences 常去城市
    preferred_dest: list[str] = []
    try:
        async with get_session() as db:
            prefs = await LongTermMemory(db).get_preferences(user_id) or {}
            preferred_dest = list(prefs.get("frequent_cities") or [])
    except Exception:
        pass

    # 构造路线优先队列：偏好目的地排前面，其余按默认顺序
    routes = list(_HOT_ROUTES)
    if preferred_dest:
        pref_routes = [r for r in routes if _CITY_NAMES.get(r[1], r[1]) in preferred_dest]
        other_routes = [r for r in routes if r not in pref_routes]
        routes = pref_routes + other_routes

    # 近 3 天日期
    dates = [(date.today() + timedelta(days=i + 1)).strftime("%Y-%m-%d") for i in range(3)]

    cards: list[RecCard] = []
    seen_destinations: set[str] = set()

    for origin, dest in routes:
        if dest in seen_destinations:
            continue
        best_deal: dict[str, Any] | None = None
        for d in dates:
            deals = await read_deals(origin_code=origin, destination_code=dest, depart_date=d)
            if deals:
                best_deal = deals[0]
                best_deal["depart_date"] = d
                break

        card = _build_card(origin, dest, best_deal, preferred_dest)
        cards.append(card)
        seen_destinations.add(dest)

    personalized = bool(preferred_dest) and any(
        _CITY_NAMES.get(c[1], c[1]) in preferred_dest for c in routes[:2]
    )

    # 兜底：没有真实数据时返回空壳卡片而不是崩溃
    return RecommendationsResponseDto(
        personalized=personalized,
        cards=cards,
    )


def _build_card(
    origin: str,
    dest: str,
    deal: dict[str, Any] | None,
    preferred_dest: list[str],
) -> RecCard:
    origin_name = _CITY_NAMES.get(origin, origin)
    dest_name = _CITY_NAMES.get(dest, dest)
    tags = list(_ROUTE_TAGS.get((origin, dest), []))
    is_personalized = dest_name in preferred_dest
    if is_personalized:
        tags.insert(0, "符合偏好")

    discount_pct: int | None = None
    preview_deal: dict[str, Any] | None = None

    if deal:
        price = deal.get("lowest_price", 0)
        avg = deal.get("history_avg_90d")
        if avg and avg > 0 and price > 0:
            discount_pct = round((avg - price) / avg * 100)

        platform = ""
        prices = deal.get("prices") or []
        if prices:
            cheapest = min(prices, key=lambda p: p.get("price", 999999))
            platform = cheapest.get("platform", "")

        preview_deal = {
            "id": f"rec-{origin}-{dest}-{deal.get('depart_date', '')}",
            "system_id": f"{deal.get('flight_no', '')}-{deal.get('depart_date', '')}",
            "platform": platform,
            "origin_city": origin_name,
            "origin_code": origin,
            "destination_city": dest_name,
            "destination_code": dest,
            "depart_date": deal.get("depart_date", ""),
            "airline": deal.get("airline", ""),
            "depart_time": deal.get("dep_time", ""),
            "arrive_time": deal.get("arr_time", ""),
            "price": price,
            "tax": 50,
            "baggage_fee": 0,
            "has_baggage": True,
            "recommend_score": str(round(8.5 + (discount_pct or 0) / 20, 1)) if discount_pct else "8.5",
            "prices": [
                {"name": p.get("platform", ""), "price": p.get("price", 0), "lowest": p.get("lowest", False)}
                for p in prices
            ],
            "signals": (["历史低价"] if discount_pct and discount_pct >= 10 else []),
        }

    reason = _build_reason(dest_name, discount_pct, is_personalized, deal)

    return RecCard(
        id=str(uuid.uuid4())[:8],
        title=f"{origin_name}→{dest_name}",
        reason=reason,
        tags=tags,
        discount_pct=discount_pct,
        preview_deal=preview_deal,
    )


def _build_reason(
    dest: str,
    discount_pct: int | None,
    is_personalized: bool,
    deal: dict[str, Any] | None,
) -> str:
    if is_personalized and discount_pct and discount_pct >= 10:
        return f"你常去的 {dest}，当前价格比均价低 {discount_pct}%，出发时机不错"
    if is_personalized:
        return f"你经常飞 {dest}，近期有席位，价格稳定"
    if discount_pct and discount_pct >= 15:
        return f"AI 监测到 {dest} 机票近期大幅低于历史均价 {discount_pct}%，值得关注"
    if discount_pct and discount_pct >= 5:
        return f"{dest} 近日机票略低于历史均价，可考虑出行"
    if deal:
        return f"{dest} 热门目的地，近期有充足席位，价格正常"
    return f"{dest} 热门出行目的地，AI 持续监控中"
