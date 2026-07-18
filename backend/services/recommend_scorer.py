"""recommend_score 计算 + deals 排序（PRD 7.1）。"""
from __future__ import annotations

from typing import Any


def _num(value: Any, default: float = 0.0) -> float:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return default
    return default


def calc_recommend_score(
    flight: dict[str, Any],
    pref_result: dict[str, Any] | None,
) -> str:
    """
    recommend_score = (历史低价原始分×0.5 + 偏好匹配原始分×0.3 + 加成原始分×0.2) × 10

    历史低价原始分 = max(0, 1 - lowest_price / history_avg_90d)  # 历史数据不足时为 0
    偏好匹配原始分 = min(matched_count, 3) / 3                    # 0~1
    加成原始分     = (stops==0 ? 1:0)×0.5 + (baggage_fee==0 ? 1:0)×0.5  # 0~1
    """
    lowest = _num(flight.get("lowest_price", flight.get("price", 0)))
    avg_90d = _num(flight.get("history_avg_90d"))

    if avg_90d and avg_90d > 0:
        hist_raw = max(0.0, 1.0 - lowest / avg_90d)
    else:
        hist_raw = 0.0

    matched_count = len(pref_result.get("reasons", [])) if pref_result else 0
    pref_raw = min(matched_count, 3) / 3.0

    stops_bonus = 1.0 if _num(flight.get("stops", 0)) == 0 else 0.0
    baggage_fee = flight.get("baggage_fee")
    baggage_bonus = (
        1.0
        if not isinstance(baggage_fee, bool)
        and isinstance(baggage_fee, (int, float))
        and baggage_fee == 0
        else 0.0
    )
    bonus_raw = stops_bonus * 0.5 + baggage_bonus * 0.5

    score = (hist_raw * 0.5 + pref_raw * 0.3 + bonus_raw * 0.2) * 10
    return f"{round(score, 1):.1f}"


def sort_deals(
    flights: list[dict[str, Any]],
    pref_results: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    排序规则（PRD 7.1）：
    1. 综合总价（price + tax + baggage_fee）升序
    2. boost=true 同等价位优先
    3. recommend_score 降序
    """
    pref_map: dict[str, dict[str, Any]] = {}
    for p in pref_results:
        key = p.get("flight_no", "")
        if key:
            pref_map[key] = p

    for f in flights:
        flight_key = f.get("flight_no", f.get("id", ""))
        pref = pref_map.get(flight_key)
        f["recommend_score"] = calc_recommend_score(f, pref)
        f["_boost"] = pref.get("boost", False) if pref else False

    def sort_key(f: dict[str, Any]) -> tuple:
        total = _num(f.get("price")) + _num(f.get("tax")) + _num(f.get("baggage_fee"))
        boost = 0 if f.get("_boost") else 1  # boost=True 排前
        score = -float(f.get("recommend_score", "0") or "0")
        return (total, boost, score)

    flights.sort(key=sort_key)

    for f in flights:
        f.pop("_boost", None)

    return flights
