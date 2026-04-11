from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List


class RecommendationService:
    def __init__(self, memory_service) -> None:
        self.memory_service = memory_service

    async def get_cards(self, user_id: str) -> Dict[str, Any]:
        preferences = await self.memory_service.get_preferences_map(user_id)
        frequent_destinations = preferences.get("frequent_destinations", [])
        price_anchor = preferences.get("price_anchor")

        cards: List[Dict[str, Any]] = [
            {
                "title": "热门低价机会",
                "reason": "适合拿来做首页首屏展示",
                "query_hint": "五一去三亚，600以内",
                "price": 399,
                "destination": "SYX",
                "tags": ["热门", "低价"],
            }
        ]

        for destination in frequent_destinations[:2]:
            cards.append(
                {
                    "title": "猜你会继续关注 {destination}".format(destination=destination),
                    "reason": "根据长期偏好自动生成",
                    "query_hint": "{destination} 下周末".format(destination=destination),
                    "price": price_anchor,
                    "destination": destination,
                    "tags": ["个性化", "记忆"],
                }
            )

        return {
            "user_id": user_id,
            "cards": cards,
            "source": "memory+mock",
            "generated_at": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        }
