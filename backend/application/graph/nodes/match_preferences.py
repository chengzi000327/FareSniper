"""Preference matching node."""

from __future__ import annotations

from backend.application.contracts.preference import (
    PreferenceMatchItem,
    PreferenceMatchResult,
)
from backend.application.graph.state import WorkflowState
from backend.services.holiday import is_holiday
from backend.services.recommend_scorer import sort_deals


async def run_preference_match(state: WorkflowState) -> WorkflowState:
    search_result = state.get("search_result")
    if not search_result or not search_result.candidates:
        return {**state, "pref_result": PreferenceMatchResult()}

    ctx = state.get("context")
    memory_facts = ctx.memory_facts if ctx else {}

    raw_flights = [c.model_dump() for c in search_result.candidates]
    from backend.services.preference_matcher import run_preference_match as _match

    raw_pref = _match(raw_flights, memory_facts)

    for c in search_result.candidates:
        c.is_holiday = is_holiday(c.depart_date)

    raw_sorted = sort_deals(raw_flights, raw_pref)
    order = {f["flight_no"]: i for i, f in enumerate(raw_sorted)}
    score_map = {f["flight_no"]: f.get("recommend_score", "0.0") for f in raw_sorted}
    search_result.candidates.sort(key=lambda c: order.get(c.flight_no, 999))
    for c in search_result.candidates:
        c.recommend_score = score_map.get(c.flight_no, "0.0")

    items = [
        PreferenceMatchItem(
            flight_no=p.get("flight_no", ""),
            matched=p.get("matched", False),
            boost=p.get("boost", False),
            reasons=p.get("reasons", []),
        )
        for p in raw_pref
    ]
    return {**state, "pref_result": PreferenceMatchResult(items=items)}
