from __future__ import annotations

from typing import Dict, List, Optional


def match_preference(
    flights: List[Dict[str, object]],
    preferences: Dict[str, object],
    query: Dict[str, object],
) -> Dict[str, object]:
    price_anchor = preferences.get("price_anchor")
    frequent_destinations = preferences.get("frequent_destinations", [])
    matched_destinations = []
    notes = []
    score = 0.4
    within_budget = False

    if query.get("destination") and query["destination"] in frequent_destinations:
        matched_destinations.append(query["destination"])
        score += 0.25
        notes.append("命中常搜目的地")

    current_min_price = None
    if flights:
        current_min_price = min(int(flight["price"]) for flight in flights if flight.get("price") is not None)

    budget = query.get("budget")
    effective_anchor = budget if budget is not None else price_anchor

    if effective_anchor is not None and current_min_price is not None:
        within_budget = current_min_price <= int(effective_anchor)
        if within_budget:
            score += 0.25
            notes.append("最低价在预算内")
        else:
            notes.append("最低价高于预算")

    if preferences.get("preferred_cabin"):
        score += 0.1
        notes.append("存在舱位偏好")

    return {
        "match_score": round(min(score, 1.0), 2),
        "within_budget": within_budget,
        "price_anchor": effective_anchor,
        "matched_destinations": matched_destinations,
        "notes": notes,
    }
