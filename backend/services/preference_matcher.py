"""PreferenceMatch：纯工程规则，无 LLM 调用（PRD 6.2）。"""
from __future__ import annotations

from typing import Any


def match_preferences(flight: dict[str, Any], user_memory: dict[str, Any]) -> dict[str, Any]:
    """计算单个航班与用户偏好的匹配情况。

    返回结构与 PRD 6.2 一致：
      { flight_no, matched, boost, reasons }
    """
    reasons: list[str] = []
    boost = False

    budget = user_memory.get("budget")
    if budget and flight.get("lowest_price", flight.get("price", 0)) <= budget:
        reasons.append("在你的心理价位以内")

    preferred_airlines = user_memory.get("preferred_airlines") or []
    if flight.get("airline") in preferred_airlines:
        reasons.append(f"你常飞的{flight['airline']}")

    constraints = user_memory.get("constraints") or []
    if "avoid_redeye" in constraints:
        dep_time = flight.get("depart_time", "00:00")
        try:
            dep_hour = int(dep_time.split(":")[0])
            if dep_hour >= 6:
                reasons.append("符合你的出行习惯")
        except (ValueError, IndexError):
            pass

    frequent_cities = user_memory.get("frequent_cities") or []
    if flight.get("destination_city") in frequent_cities:
        boost = True  # 不输出 reason，仅影响排序权重

    return {
        "flight_no": flight.get("flight_no", flight.get("id", "")),
        "matched": len(reasons) > 0,
        "boost": boost,
        "reasons": reasons[:3],
    }


def run_preference_match(
    flights: list[dict[str, Any]],
    user_memory: dict[str, Any],
) -> list[dict[str, Any]]:
    """批量偏好匹配，user_memory 为空时返回空列表。"""
    if not user_memory:
        return []
    return [match_preferences(f, user_memory) for f in flights]
