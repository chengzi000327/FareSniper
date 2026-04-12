from __future__ import annotations

from agentscope.message import Msg

from backend.agents.base import FareSniperAgent


class PreferenceMatchSkill(FareSniperAgent):
    """
    将搜索结果与用户偏好对比，计算匹配分数和价格分析。
    输入：context dict（含 intent + flight_search 结果）
    输出：{"match_score": float, "within_budget": bool, "matched_preferences": [...], ...}
    """

    async def reply(self, msg: Msg) -> Msg:
        context = msg.metadata if isinstance(msg.metadata, dict) else {}
        results = context.get("results", {})
        intent = context.get("intent", {})

        deals = results.get("flight_search", {}).get("deals", [])
        preferences = results.get("memory_query", {}).get("preferences", {})

        analysis = self._analyze(deals, intent, preferences)

        import json
        return Msg(
            name="preference_match",
            content=json.dumps(analysis, ensure_ascii=False),
            role="assistant",
            metadata=analysis,
        )

    def _analyze(self, deals: list, intent: dict, preferences: dict) -> dict:
        prices = [d.get("price", 0) for d in deals if d.get("price")]
        budget = intent.get("budget") or preferences.get("price_anchor")

        min_price = min(prices) if prices else None
        max_price = max(prices) if prices else None
        avg_price = int(sum(prices) / len(prices)) if prices else None
        within_budget = bool(budget and min_price and min_price <= budget)

        return {
            "min_price": min_price,
            "max_price": max_price,
            "avg_price": avg_price,
            "avg_90d": None,
            "lower_than_avg": None,
            "price_spread_pct": None,
            "match_score": 0.5,
            "within_budget": within_budget,
            "matched_preferences": [],
        }
