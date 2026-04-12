from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from backend.memory.long_term import FIELD_LABELS, LongTermMemory

_DESTINATION_CITY_MAP = {
    "SYX": "三亚", "PEK": "北京", "SHA": "上海", "CAN": "广州",
    "CTU": "成都", "NRT": "东京", "ICN": "首尔", "HKG": "香港",
    "SIN": "新加坡", "BJS": "北京",
}


class RecommendationService:
    def __init__(
        self,
        session_factory=None,
        redis_client=None,
        # 向后兼容旧参数
        memory_service=None,
    ) -> None:
        self.session_factory = session_factory
        self.redis_client = redis_client

    # ── Memory endpoints ──────────────────────────────────────────────────

    async def get_memory(self, user_id: str) -> Dict[str, Any]:
        now = _now()
        memories: List[Dict[str, Any]] = []
        query_history: List[Dict[str, Any]] = []
        click_history: List[Dict[str, Any]] = []

        if self.session_factory:
            try:
                async with self.session_factory() as session:
                    ltm = LongTermMemory(session)
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
        self,
        user_id: str,
        field: str,
        value: Any,
        source: str = "manual",
    ) -> Dict[str, Any]:
        if self.session_factory:
            try:
                async with self.session_factory() as session:
                    ltm = LongTermMemory(session)
                    await ltm.upsert_preferences(user_id, {field: value})
                    await session.commit()
            except Exception:
                pass
        return await self.get_memory(user_id)

    async def delete_memory_field(self, user_id: str, field: str) -> Dict[str, Any]:
        if self.session_factory:
            try:
                async with self.session_factory() as session:
                    ltm = LongTermMemory(session)
                    # Clear the field by setting it to None / empty
                    _clear: Any = [] if field in {
                        "preferred_origins", "preferred_destinations", "frequent_destinations"
                    } else None
                    await ltm.upsert_preferences(user_id, {field: _clear})
                    await session.commit()
            except Exception:
                pass
        return await self.get_memory(user_id)

    # ── Recommendation cards ──────────────────────────────────────────────

    async def get_cards(self, user_id: str) -> Dict[str, Any]:
        now = _now()
        cards: List[Dict[str, Any]] = []
        prefs: Dict[str, Any] = {}

        if self.session_factory:
            try:
                async with self.session_factory() as session:
                    ltm = LongTermMemory(session)
                    prefs = await ltm.get_preferences(user_id) or {}
            except Exception:
                pass

        # Static featured card
        cards.append({
            "id": str(uuid.uuid4()),
            "title": "热门低价机会",
            "reason": "当前五一三亚机票价格低于历史均价 18%",
            "query_hint": "五一去三亚，600以内",
            "tags": ["热门", "低价"],
            "preview_deal": None,
        })

        # Personalized cards from frequent destinations
        frequent = prefs.get("frequent_destinations") or []
        price_anchor: Optional[int] = prefs.get("price_anchor")

        for dest_code in frequent[:2]:
            dest_city = _DESTINATION_CITY_MAP.get(dest_code, dest_code)
            cards.append({
                "id": str(uuid.uuid4()),
                "title": f"猜你会继续关注 {dest_city}",
                "reason": "根据长期偏好自动生成",
                "query_hint": f"去{dest_city}，下周末出发",
                "tags": ["个性化", "记忆"],
                "preview_deal": None,
            })

        # Budget reminder card
        if price_anchor:
            cards.append({
                "id": str(uuid.uuid4()),
                "title": f"为你找到 {price_anchor} 元以内的机票",
                "reason": f"根据你的心理价位 ¥{price_anchor} 智能筛选",
                "query_hint": f"下周末出发，{price_anchor}以内",
                "tags": ["预算", "智能"],
                "preview_deal": None,
            })

        return {
            "user_id": user_id,
            "cards": cards,
            "meta": {
                "generated_at": now,
                "source": "memory+mock",
                "result_count": len(cards),
            },
        }


# ── helpers ───────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _prefs_to_memory_items(prefs: Dict[str, Any]) -> List[Dict[str, Any]]:
    now = _now()
    items: List[Dict[str, Any]] = []
    for field, label in FIELD_LABELS.items():
        value = prefs.get(field)
        if value is None:
            continue
        if isinstance(value, list) and not value:
            continue
        if isinstance(value, list):
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
