from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from backend.data_sources.mock_flights import get_mock_flights
from backend.memory.long_term import FIELD_LABELS, LongTermMemory

# 冷启动热门路线（不只是北京出发，PRD 8.6）
_COLD_START_ROUTES = [
    ("北京", "BJS", "三亚",  "SYX", "五一去三亚，600以内，最好直飞",   ["热门", "直飞"]),
    ("北京", "BJS", "成都",  "CTU", "北京飞成都，下个月出发",           ["热门", "特价"]),
    ("上海", "SHA", "三亚",  "SYX", "上海去三亚，五一假期",             ["热门", "节假日"]),
    ("成都", "CTU", "杭州",  "HGH", "成都到杭州，下周末",               ["小众", "直飞"]),
    ("广州", "CAN", "北京",  "BJS", "广州飞北京，工作出差",             ["商务", "直飞"]),
    ("北京", "BJS", "广州",  "CAN", "北京去广州，下个月底出发",         ["特价", "热门"]),
    ("北京", "BJS", "杭州",  "HGH", "北京飞杭州，国庆假期",             ["热门", "节假日"]),
    ("北京", "BJS", "上海",  "SHA", "北京去上海，这周末",               ["高铁替代", "直飞"]),
]

_DEPART_DATE_DEFAULT = "2026-05-01"


class RecommendationService:
    def __init__(
        self,
        session_factory=None,
        redis_client=None,
        memory_service=None,
    ) -> None:
        self.session_factory = session_factory
        self.redis_client = redis_client

    # ── Memory endpoints ──────────────────────────────────────────────────

    async def get_memory(self, user_id: str) -> dict[str, Any]:
        now = _now()
        memories: list[dict[str, Any]] = []
        query_history: list[dict[str, Any]] = []
        click_history: list[dict[str, Any]] = []

        if self.session_factory:
            try:
                async with self.session_factory() as db:
                    ltm = LongTermMemory(db)
                    prefs = await ltm.get_preferences(user_id) or {}
                    memories = _prefs_to_memory_items(prefs)

                    raw_queries = await ltm.get_recent_queries(user_id)
                    query_history = [
                        {
                            "query": {"text": r.get("query_text", ""), **r.get("intent", {})},
                            "created_at": r.get("created_at", now),
                        }
                        for r in raw_queries
                    ]

                    raw_clicks = await ltm.get_recent_clicks(user_id)
                    click_history = [
                        {
                            "flight_info": r.get("flight_data", {}),
                            "created_at": r.get("clicked_at", now),
                        }
                        for r in raw_clicks
                    ]
            except Exception:
                pass

        return {
            "user_id": user_id,
            "memories": memories,
            "query_history": query_history,
            "click_history": click_history,
            "meta": {"generated_at": now, "source": "postgresql"},
        }

    async def patch_memory(
        self, user_id: str, field: str, value: Any, source: str = "manual"
    ) -> dict[str, Any]:
        if self.session_factory:
            try:
                async with self.session_factory() as db:
                    ltm = LongTermMemory(db)
                    await ltm.upsert_preferences(user_id, {field: value})
                    await db.commit()
            except Exception:
                pass
        return await self.get_memory(user_id)

    async def delete_memory_field(self, user_id: str, field: str) -> dict[str, Any]:
        if self.session_factory:
            try:
                async with self.session_factory() as db:
                    ltm = LongTermMemory(db)
                    _clear: Any = [] if field in {
                        "frequent_cities", "preferred_airlines", "constraints", "travel_scenes"
                    } else None
                    await ltm.upsert_preferences(user_id, {field: _clear})
                    await db.commit()
            except Exception:
                pass
        return await self.get_memory(user_id)

    # ── Recommendation cards ──────────────────────────────────────────────

    async def get_cards(self, user_id: str) -> dict[str, Any]:
        now = _now()
        prefs: dict[str, Any] = {}

        if self.session_factory:
            try:
                async with self.session_factory() as db:
                    ltm = LongTermMemory(db)
                    prefs = await ltm.get_preferences(user_id) or {}
            except Exception:
                pass

        is_cold_start = not prefs or not any([
            prefs.get("frequent_cities"),
            prefs.get("budget"),
            prefs.get("preferred_airlines"),
        ])

        if is_cold_start:
            cards = self._build_cold_start_cards()
        else:
            cards = self._build_personalized_cards(prefs)

        return {
            "user_id": user_id,
            "cards": cards,
            "meta": {"generated_at": now, "source": "mock", "result_count": len(cards)},
        }

    def _build_cold_start_cards(self) -> list[dict[str, Any]]:
        cards = []
        for origin_city, origin_code, dest_city, dest_code, query_hint, tags in _COLD_START_ROUTES:
            preview = _make_preview_deal(origin_city, origin_code, dest_city, dest_code)
            if preview is None:
                continue
            cards.append({
                "id": str(uuid.uuid4()),
                "title": f"{origin_city} → {dest_city} 特价",
                "reason": f"{dest_city}近期出现低价窗口，性价比极高",
                "query_hint": query_hint,
                "tags": tags,
                "preview_deal": preview,
            })
            if len(cards) >= 8:
                break
        return cards

    def _build_personalized_cards(self, prefs: dict[str, Any]) -> list[dict[str, Any]]:
        cards: list[dict[str, Any]] = []
        budget = prefs.get("budget")
        frequent_cities: list[str] = prefs.get("frequent_cities") or []

        # 偏好城市卡片
        for city in frequent_cities[:3]:
            preview = _make_preview_deal("北京", "BJS", city, _city_to_code(city))
            if preview is None:
                continue
            query_hint = f"北京去{city}"
            if budget:
                query_hint += f"，{budget}以内"
            cards.append({
                "id": str(uuid.uuid4()),
                "title": f"猜你要去 {city}",
                "reason": f"根据你的出行记录，{city}是你常去的目的地",
                "query_hint": query_hint,
                "tags": ["个性化", "常去"],
                "preview_deal": preview,
            })

        # 预算提醒卡片
        if budget:
            preview = _make_preview_deal("北京", "BJS", "三亚", "SYX")
            if preview:
                cards.append({
                    "id": str(uuid.uuid4()),
                    "title": f"{budget}元以内特价票",
                    "reason": f"根据你的心理价位 ¥{budget} 智能筛选",
                    "query_hint": f"三亚，五一，{budget}以内",
                    "tags": ["预算", "智能"],
                    "preview_deal": preview,
                })

        # 不足 4 张时用冷启动补齐
        cold = self._build_cold_start_cards()
        for card in cold:
            if len(cards) >= 8:
                break
            if not any(c["query_hint"] == card["query_hint"] for c in cards):
                cards.append(card)

        return cards[:8]


# ── helpers ───────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_CITY_CODE_MAP = {
    "三亚": "SYX", "北京": "BJS", "上海": "SHA", "广州": "CAN",
    "成都": "CTU", "杭州": "HGH",
}


def _city_to_code(city: str) -> str:
    return _CITY_CODE_MAP.get(city, city)


def _make_preview_deal(
    origin_city: str,
    origin_code: str,
    dest_city: str,
    dest_code: str,
) -> dict[str, Any] | None:
    try:
        flights = get_mock_flights(origin_city, dest_city, _DEPART_DATE_DEFAULT)
        if not flights:
            return None
        f = flights[0]
        return f
    except Exception:
        return None


def _prefs_to_memory_items(prefs: dict[str, Any]) -> list[dict[str, Any]]:
    now = _now()
    items = []
    for field, label in FIELD_LABELS.items():
        value = prefs.get(field)
        if value is None:
            continue
        if isinstance(value, list) and not value:
            continue

        if field == "budget":
            value_display = f"¥{value}以内"
        elif isinstance(value, list):
            value_display = "、".join(str(v) for v in value)
        else:
            value_display = str(value)

        items.append({
            "id": field,
            "field": field,
            "label": label,
            "value": value,
            "value_display": value_display,
            "source": "auto",
            "updated_at": now,
        })
    return items
