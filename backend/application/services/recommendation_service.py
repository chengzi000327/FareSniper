from __future__ import annotations

import json
import hashlib
import statistics
import uuid
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from backend.application.contracts.recommendations import RecCard, RecommendationsResponseDto
from backend.application.contracts.flight_provider import is_complete_https_url
from backend.application.services._routes import CITY_NAMES, HOT_ROUTES, ROUTE_TAGS
from backend.config import settings
from backend.infrastructure.db.base import get_session
from backend.infrastructure.db.flight_snapshot_repo import read_deals
from backend.infrastructure.redis.session_store import _redis
from backend.memory.long_term import LongTermMemory
from backend.services.booking_url_builder import Platform, build_booking_url
from backend.schemas.common import DealCardDto

# ── 缓存分层 ──────────────────────────────────────────────────────────────────
# L1:全局未排序卡片池,全用户共享,key=rec:pool:v1,TTL 600s。
# L2:请求时在内存里做个性化排序(读 frequent_cities),不进 L1 缓存。
POOL_CACHE_KEY = "rec:pool:v3"
POOL_CACHE_TTL = 600  # 10 分钟

DEFAULT_LIMIT = 6

# 折扣样本下限:同航线可比价样本不足时不计折扣(避免单点数据失真)
_MIN_DISCOUNT_SAMPLE = 3
# 折扣封顶:离群特价相对基准可能算出 70%+ 的失真数字,封顶到 50% 更可感知
_DISCOUNT_CAP = 50

# 平台名(英文 slug / 中文别名)→ booking_url_builder.Platform
_PLATFORM_ALIASES: dict[str, Platform] = {
    "ctrip": Platform.CTRIP, "携程": Platform.CTRIP,
    "qunar": Platform.QUNAR, "去哪儿": Platform.QUNAR,
    "tongcheng": Platform.TONGCHENG, "同程": Platform.TONGCHENG,
    "fliggy": Platform.FLIGGY, "飞猪": Platform.FLIGGY,
    "umetrip": Platform.UMETRIP, "航旅纵横": Platform.UMETRIP,
}


async def build_recommendations(
    user_id: str, *, limit: int = DEFAULT_LIMIT, offset: int = 0
) -> RecommendationsResponseDto:
    """构建探索页瀑布流分页响应。

    流程:L1 拿全局卡片池(命中缓存或现算) → L2 内存个性化排序 →
    按 limit/offset 切片 → 计算 has_more/next_offset。
    """
    pool = await _get_card_pool()
    renderable = [
        card
        for card in pool
        if card.preview_deal is not None
        and _is_future_departure(card.preview_deal.get("depart_date"))
    ]
    ordered, personalized = await _personalize(user_id, renderable)

    total = len(ordered)
    page = ordered[offset : offset + limit]
    next_offset = offset + len(page)
    has_more = next_offset < total

    return RecommendationsResponseDto(
        personalized=personalized,
        cards=page,
        has_more=has_more,
        next_offset=next_offset,
    )


async def _get_card_pool() -> list[RecCard]:
    """L1:返回全局未排序卡片池,优先读 rec:pool:v1 缓存。"""
    try:
        raw = await _redis().get(POOL_CACHE_KEY)
        if raw:
            return [RecCard.model_validate(c) for c in json.loads(raw)]
    except Exception:
        pass

    pool = await _build_card_pool()

    try:
        payload = json.dumps([c.model_dump() for c in pool])
        await _redis().setex(POOL_CACHE_KEY, POOL_CACHE_TTL, payload)
    except Exception:
        pass
    return pool


async def _build_card_pool() -> list[RecCard]:
    """遍历全部热门路线,生成未排序、未个性化的卡片池。"""
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date()
    dates = [
        (today + timedelta(days=i + 1)).isoformat() for i in range(3)
    ]

    cards: list[RecCard] = []
    seen_destinations: set[str] = set()

    for origin, dest in HOT_ROUTES:
        if dest in seen_destinations:
            continue

        batch: list[dict[str, Any]] = []
        chosen_date: str | None = None
        for d in dates:
            deals = await read_deals(origin_code=origin, destination_code=dest, depart_date=d)
            if deals:
                batch = deals
                chosen_date = d
                break
        best_deal: dict[str, Any] | None = None
        market_avg: int | None = None
        sample_n = 0
        if batch:
            selected_currency = _preferred_batch_currency(batch)
            comparable_batch = [
                deal
                for deal in batch
                if _deal_currency(deal) == selected_currency
                and _positive_price(deal.get("lowest_price")) is not None
            ]
            fresh_batch = [
                deal
                for deal in comparable_batch
                if _deal_freshness(deal) == "fresh"
                and isinstance(deal.get("winning_price_id"), str)
            ]
            selection_pool = fresh_batch or comparable_batch
            if selection_pool:
                best_deal = dict(
                    min(
                        selection_pool,
                        key=lambda deal: _positive_price(
                            deal.get("lowest_price")
                        ),
                    )
                )
                best_deal["depart_date"] = chosen_date
            # 当批中位数作为折扣基准的最后一层兜底——同一天的高价商务/全价舱
            # 会把均值拉高导致折扣虚高,中位数对离群价更稳健。
            prices = [
                price
                for deal in fresh_batch
                if (price := _positive_price(deal.get("lowest_price")))
                is not None
            ]
            sample_n = len(prices)
            if prices:
                market_avg = round(statistics.median(prices))

        cards.append(_build_card(origin, dest, best_deal, market_avg, sample_n))
        seen_destinations.add(dest)

    return cards


async def _personalize(user_id: str, pool: list[RecCard]) -> tuple[list[RecCard], bool]:
    """L2:读 frequent_cities,把偏好目的地排前面并打"符合偏好"标签。

    在内存里对 L1 池做个性化,不写回 L1(避免污染全局共享池)。
    """
    preferred_dest: list[str] = []
    try:
        async with get_session() as db:
            prefs = await LongTermMemory(db).get_preferences(user_id) or {}
            preferred_dest = list(prefs.get("frequent_cities") or [])
    except Exception:
        pass

    if not preferred_dest:
        return list(pool), False

    pref_cards: list[RecCard] = []
    other_cards: list[RecCard] = []
    for card in pool:
        dest_name = card.title.split("→")[-1]
        if dest_name in preferred_dest:
            personalized_card = card.model_copy(deep=True)
            if "符合偏好" not in personalized_card.tags:
                personalized_card.tags.insert(0, "符合偏好")
            pref_cards.append(personalized_card)
        else:
            other_cards.append(card)

    personalized = bool(pref_cards)
    return pref_cards + other_cards, personalized


def _build_card(
    origin: str,
    dest: str,
    deal: dict[str, Any] | None,
    market_avg: int | None,
    sample_n: int,
) -> RecCard:
    origin_name = CITY_NAMES.get(origin, origin)
    dest_name = CITY_NAMES.get(dest, dest)
    tags = list(ROUTE_TAGS.get((origin, dest), []))

    discount_pct: int | None = None
    preview_deal: dict[str, Any] | None = None
    is_history_low = False

    if deal and not _is_future_departure(deal.get("depart_date")):
        deal = None

    if deal:
        currency = _deal_currency(deal)
        if not currency:
            return RecCard(
                id=str(uuid.uuid4())[:8],
                title=f"{origin_name}→{dest_name}",
                reason=_build_reason(dest_name, None, None, False),
                tags=tags,
            )
        prices = deal.get("prices") or []
        selected_prices = [
            row
            for row in prices
            if str(row.get("currency") or "").upper() == currency
        ]
        winning_price = _winning_price(deal, selected_prices)
        price = (
            _positive_price(winning_price.get("price"))
            if winning_price is not None
            else None
        )
        if winning_price is not None and price is None:
            winning_price = None
        if winning_price is not None:
            discount_pct = _compute_discount(deal, market_avg, sample_n)

        # "历史低价"信号改用 history_low_90d 判定:价格触及 90 天历史低点
        hist_low = deal.get("history_low_90d")
        is_history_low = bool(
            winning_price is not None
            and hist_low
            and price is not None
            and price <= hist_low
        )

        platform_name, booking_url = _build_booking(
            deal, winning_price, origin, dest
        )

        winning_price_id = (
            str(winning_price["id"])
            if winning_price is not None
            else None
        )
        deal_freshness = _deal_freshness(deal)
        preview_deal = {
            "id": f"rec-{origin}-{dest}-{deal.get('depart_date', '')}",
            "system_id": f"{deal.get('flight_no', '')}-{deal.get('depart_date', '')}",
            "flight_no": deal.get("flight_no", ""),
            "platform": platform_name,
            "origin_city": origin_name,
            "origin_code": origin,
            "destination_city": dest_name,
            "destination_code": dest,
            "depart_date": deal.get("depart_date", ""),
            "airline": deal.get("airline", ""),
            "depart_time": deal.get("dep_time", ""),
            "arrive_time": deal.get("arr_time", ""),
            "duration_minutes": None,
            "stops": int(deal.get("stops", 0)),
            "price": price,
            "lowest_price": price,
            "tax": None,
            "baggage_fee": None,
            "has_baggage": None,
            "total_price": price,
            "currency": currency,
            "recommend_score": None,
            "winning_price_id": winning_price_id,
            "prices": [
                {
                    "id": _recommendation_price_id(p, currency),
                    "name": p.get("platform", ""),
                    "price": p.get("price"),
                    "currency": currency,
                    "lowest": (
                        winning_price_id is not None
                        and _recommendation_price_id(p, currency)
                        == winning_price_id
                    ),
                    "price_status": (
                        p.get("price_status", "priced")
                        if _price_freshness(p) == "fresh"
                        else "stale"
                    ),
                    "provider_status": (
                        "success"
                        if _price_freshness(p) == "fresh"
                        else "stale"
                    ),
                    "url": (
                        booking_url
                        if winning_price_id is not None
                        and _recommendation_price_id(p, currency)
                        == winning_price_id
                        else p.get("url")
                        if _price_freshness(p) == "fresh"
                        and is_complete_https_url(p.get("url"))
                        else None
                    ),
                    "data_provider": p.get("data_provider", "legacy"),
                    "data_freshness": _price_freshness(p),
                }
                for p in selected_prices
            ],
            "signals": (["历史低价"] if is_history_low else []),
            "booking_url": booking_url,
            "h5_fallback_url": booking_url,
            "data_freshness": deal_freshness,
        }
        preview_deal = DealCardDto.model_validate(preview_deal).model_dump(
            mode="json"
        )

    reason = _build_reason(
        dest_name,
        discount_pct,
        deal if preview_deal and preview_deal["winning_price_id"] else None,
        is_history_low,
    )

    return RecCard(
        id=str(uuid.uuid4())[:8],
        title=f"{origin_name}→{dest_name}",
        reason=reason,
        tags=tags,
        discount_pct=discount_pct,
        preview_deal=preview_deal,
    )


def _compute_discount(deal: dict[str, Any], market_avg: int | None, sample_n: int) -> int | None:
    """折扣基准分级:history_avg_90d → 当批中位数;样本<3 不计折扣。

    优先用 90 天历史均价(最权威);缺失时退回同航线当批中位数,但样本量
    不足(<3)时基准不可信,直接返 null。封顶 50%。
    """
    price = deal.get("lowest_price", 0)
    if price <= 0:
        return None

    avg = deal.get("history_avg_90d")
    if not avg:
        # 退回当批中位数,但样本太少则放弃(基准不可信)
        if sample_n < _MIN_DISCOUNT_SAMPLE:
            return None
        avg = market_avg

    if avg and avg > 0 and avg > price:
        return min(round((avg - price) / avg * 100), _DISCOUNT_CAP)
    return None


def _is_future_departure(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        departure = datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return False
    return departure > datetime.now(ZoneInfo("Asia/Shanghai")).date()


def _deal_currency(deal: dict[str, Any]) -> str | None:
    direct = deal.get("currency")
    if isinstance(direct, str) and len(direct.strip()) == 3:
        return direct.strip().upper()
    currencies = sorted(
        {
            str(price.get("currency")).strip().upper()
            for price in deal.get("prices") or []
            if isinstance(price.get("currency"), str)
            and len(str(price.get("currency")).strip()) == 3
        }
    )
    if not currencies:
        return None
    return "CNY" if "CNY" in currencies else currencies[0]


def _preferred_batch_currency(batch: list[dict[str, Any]]) -> str | None:
    currencies = sorted(
        {
            currency
            for deal in batch
            if (currency := _deal_currency(deal)) is not None
        }
    )
    if not currencies:
        return None
    return "CNY" if "CNY" in currencies else currencies[0]


def _price_freshness(price: dict[str, Any]) -> str:
    value = price.get("data_freshness")
    return value if value in {"fresh", "stale", "unknown"} else "unknown"


def _deal_freshness(deal: dict[str, Any]) -> str:
    value = deal.get("data_freshness")
    return value if value in {"fresh", "stale", "unknown"} else "unknown"


def _winning_price(
    deal: dict[str, Any], prices: list[dict[str, Any]]
) -> dict[str, Any] | None:
    if _deal_freshness(deal) != "fresh":
        return None
    winning_price_id = deal.get("winning_price_id")
    if not isinstance(winning_price_id, str) or not winning_price_id:
        return None
    matches = [
        price
        for price in prices
        if _recommendation_price_id(price, _deal_currency(deal) or "")
        == winning_price_id
    ]
    if len(matches) != 1:
        return None
    winner = matches[0]
    if (
        _price_freshness(winner) != "fresh"
        or winner.get("price_status", "priced") != "priced"
    ):
        return None
    return winner


def _positive_price(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _recommendation_price_id(price: dict[str, Any], currency: str) -> str:
    existing = price.get("id")
    if isinstance(existing, str) and existing:
        return existing
    raw = "|".join(
        (
            str(price.get("data_provider", "legacy")),
            str(price.get("platform", "")),
            currency,
        )
    )
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _build_booking(
    deal: dict[str, Any],
    winning_price: dict[str, Any] | None,
    origin: str,
    dest: str,
) -> tuple[str, str | None]:
    """Generate a booking action from the explicit fresh winning row."""
    if (
        winning_price is None
        or _price_freshness(winning_price) != "fresh"
        or not _is_future_departure(deal.get("depart_date"))
    ):
        return "", None
    platform_name = winning_price.get("platform", "")
    direct_url = winning_price.get("url")
    if is_complete_https_url(direct_url):
        return platform_name, direct_url

    platform = _PLATFORM_ALIASES.get(str(platform_name).lower()) or _PLATFORM_ALIASES.get(platform_name)
    if not platform:
        return platform_name, None

    try:
        url = build_booking_url(
            platform,
            flight_no=deal.get("flight_no", ""),
            date=deal.get("depart_date", ""),
            origin=origin,
            destination=dest,
            user_agent="",  # 服务端生成 → 默认 H5 链接,前端 <a> 直接打开
            cps_id=settings.cps_id_default,
        )
    except Exception:
        return platform_name, None
    return platform_name, url if is_complete_https_url(url) else None


def _build_reason(
    dest: str,
    discount_pct: int | None,
    deal: dict[str, Any] | None,
    is_history_low: bool,
) -> str:
    if is_history_low:
        return f"AI 监测到 {dest} 机票触及近 90 天历史低价,出发时机难得"
    if discount_pct and discount_pct >= 15:
        return f"AI 监测到 {dest} 机票大幅低于近期均价 {discount_pct}%,值得关注"
    if discount_pct and discount_pct >= 5:
        return f"{dest} 近日机票略低于近期均价,可考虑出行"
    if deal:
        return f"{dest} 热门目的地,近期有充足席位,价格正常"
    return f"{dest} 热门出行目的地,AI 持续监控中"
