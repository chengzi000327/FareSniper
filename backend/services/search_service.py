from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from backend.tools.analyze_history import analyze_history
from backend.tools.compare_prices import compare_prices
from backend.tools.generate_signals import generate_signals
from backend.tools.match_preference import match_preference

_CITY_MAP = {
    "PEK": "北京", "SHA": "上海", "CAN": "广州", "CTU": "成都",
    "NRT": "东京", "ICN": "首尔", "HKG": "香港", "SIN": "新加坡",
    "SYX": "三亚", "BJS": "北京",
}


class SearchService:
    def __init__(
        self,
        llm_client,
        data_source_registry,
        intention_agent=None,
        orchestration_agent=None,
        session_factory=None,
        redis_client=None,
        # 向后兼容旧参数
        memory_service=None,
    ) -> None:
        self.llm_client = llm_client
        self.data_source_registry = data_source_registry
        self.session_factory = session_factory
        self.redis_client = redis_client

    async def search(self, user_id: str, message: str) -> Dict[str, Any]:
        query = await self.llm_client.parse_intent(message)
        preferences = await self._get_preferences(user_id)

        primary_source = self.data_source_registry.get("ctrip")
        flights = await primary_source.search_flights(
            origin=query["origin"],
            destination=query["destination"],
            date_start=query["date_start"],
            date_end=query["date_end"],
        )

        budget = query.get("budget")
        if budget:
            flights = [f for f in flights if int(f["price"]) <= int(budget) * 1.2]
        flights.sort(key=lambda f: int(f["price"]))

        comparison = compare_prices(flights)
        route = f"{query['origin']}-{query['destination']}"
        history_prices = await primary_source.get_history_prices(route=route, days=90)
        history = analyze_history(history_prices, comparison.get("min_price"))
        preference = match_preference(flights, preferences, query)
        signals = generate_signals(comparison, history, preference)

        for f in flights:
            f.setdefault("signals", [])
            if not f["signals"]:
                f["signals"] = list(signals[:2])

        recommendation_raw = await self.llm_client.generate_recommendation(
            flights=flights,
            preferences=preferences,
            metrics={"comparison": comparison, "history": history, "preference": preference, "signals": signals},
        )

        action_map = {"high": "buy_now", "medium": "watch", "low": "watch"}
        action = action_map.get(recommendation_raw.get("confidence", "medium"), "watch")
        now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # 补齐 DealCardDto 必需字段
        for f in flights:
            f.setdefault("system_id", "SYS.000")
            f.setdefault("origin_city", _CITY_MAP.get(query["origin"], query["origin"]))
            f.setdefault("origin_code", query["origin"])
            f.setdefault("destination_city", _CITY_MAP.get(query["destination"], query["destination"]))
            f.setdefault("destination_code", query["destination"])
            f.setdefault("verdict", "价格正常")
            f.setdefault("confidence", "medium")
            f.setdefault("original_price", None)
            f.setdefault("discount_rate", None)
            f.setdefault("booking_url", None)
            f.setdefault("cabin", "economy")
            f.setdefault("depart_date", query["date_start"])
            f.setdefault("depart_time", "00:00")
            f.setdefault("arrive_time", "00:00")
            f.setdefault("airline", "未知航司")
            f.setdefault("id", "unknown")
            f.setdefault("platform", "ctrip")

        return {
            "user_id": user_id,
            "query": {
                "raw_text": query.get("raw_text", message),
                "normalized_text": query.get("normalized_text", message),
                "origin_city": _CITY_MAP.get(query["origin"], query["origin"]),
                "origin_code": query["origin"],
                "destination_city": _CITY_MAP.get(query["destination"], query["destination"]),
                "destination_code": query["destination"],
                "date_start": query["date_start"],
                "date_end": query["date_end"],
                "budget": query.get("budget"),
            },
            "deals": flights,
            "analysis": {
                "min_price": comparison.get("min_price"),
                "max_price": comparison.get("max_price"),
                "avg_price": comparison.get("avg_price"),
                "avg_90d": history.get("avg_90d"),
                "lower_than_avg": history.get("lower_than_avg"),
                "price_spread_pct": comparison.get("price_spread_pct"),
                "match_score": preference.get("match_score", 0.0),
                "within_budget": preference.get("within_budget", False),
                "matched_preferences": preference.get("matched_destinations", []),
            },
            "recommendation": {
                "action": action,
                "text": recommendation_raw.get("recommendation", ""),
                "confidence": recommendation_raw.get("confidence", "medium"),
                "signals": recommendation_raw.get("signals", []),
            },
            "meta": {
                "generated_at": now,
                "source": primary_source.name,
                "result_count": len(flights),
                "fallback_mode": bool(flights and str(flights[0].get("id", "")).startswith("mock-")),
            },
        }

    async def _get_preferences(self, user_id: str) -> dict:
        if self.session_factory:
            try:
                async with self.session_factory() as session:
                    from backend.memory.long_term import LongTermMemory
                    ltm = LongTermMemory(session)
                    return await ltm.get_preferences(user_id) or {}
            except Exception:
                pass
        return {}
