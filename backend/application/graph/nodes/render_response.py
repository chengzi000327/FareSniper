"""Render graph state into the frontend response contract."""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone

from backend.application.contracts.decision import FrontendResponse
from backend.application.graph.state import WorkflowState


def _now() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def render_response(state: WorkflowState) -> WorkflowState:
    search_result = state.get("search_result")
    decision = state.get("decision")
    intent = state.get("intent")
    pref_result = state.get("pref_result")

    deals = []
    result_source = "mock"
    if search_result:
        # New ReAct graph: search_result is a dict from tool_router
        if isinstance(search_result, dict):
            deals = list(search_result.get("deals", []))
            result_source = search_result.get("source", "tool")
        else:
            # Old DAG graph: search_result is FlightSearchResult with .candidates
            for c in search_result.candidates:
                deal = c.model_dump()
                deal["id"] = f"deal-{c.flight_no}-{c.depart_date}"
                deal["system_id"] = f"{c.flight_no}-{c.depart_date}"
                deal["platform"] = next((p.platform for p in c.prices if p.lowest), "")
                deal["origin_city"] = c.origin_city or (
                    intent.origin.city if intent and intent.origin else ""
                )
                deal["destination_city"] = c.destination_city or (
                    intent.destination.city if intent and intent.destination else ""
                )
                deal["depart_time"] = c.depart_time
                deal["arrive_time"] = c.arrive_time
                deal["price"] = c.lowest_price
                deal["prices"] = [
                    {"name": p["platform"], "price": p["price"], "lowest": p.get("lowest", False)}
                    for p in deal.get("prices", [])
                ]
                deals.append(deal)

    prices = _extract_prices(search_result, deals)
    pref_reasons: list[str] = []
    if pref_result:
        if isinstance(pref_result, dict):
            for p in pref_result.get("filtered", []) + pref_result.get("boosted", []):
                pref_reasons.extend(p.get("reasons", []))
        else:
            for p in pref_result.items:
                pref_reasons.extend(p.reasons)

    _candidates = search_result.candidates if search_result and not isinstance(search_result, dict) else []
    avg_90d_vals = [c.history_avg_90d for c in _candidates if c.history_avg_90d]
    best = _candidates[0] if _candidates else None
    best_avg = best.history_avg_90d if best else None
    best_price = best.lowest_price if best else 0
    lower_than_avg = (
        round((best_avg - best_price) / best_avg, 4)
        if best_avg and best_price
        else None
    )

    analysis = {
        "min_price": min(prices) if prices else None,
        "max_price": max(prices) if prices else None,
        "avg_price": int(sum(prices) / len(prices)) if prices else None,
        "avg_90d": int(sum(avg_90d_vals) / len(avg_90d_vals)) if avg_90d_vals else None,
        "lower_than_avg": lower_than_avg,
        "price_spread_pct": None,
        "match_score": _match_score(pref_result, len(deals)),
        "within_budget": bool(decision and "符合心理价位" in decision.signals),
        "matched_preferences": list(set(pref_reasons)),
    }

    query_summary = None
    if intent and not intent.parse_failed:
        query_summary = {
            "raw_text": intent.raw_text,
            "normalized_text": intent.raw_text,
            "origin_city": intent.origin.city if intent.origin else "",
            "origin_code": intent.origin.iata_code if intent.origin else "",
            "destination_city": intent.destination.city if intent.destination else "",
            "destination_code": intent.destination.iata_code if intent.destination else "",
            "date_start": intent.date_window.start_date if intent.date_window else "",
            "date_end": intent.date_window.end_date if intent.date_window else "",
            "budget": intent.budget_cny,
        }

    recommendation = {}
    if decision:
        recommendation = {
            "action": decision.action.value,
            "text": decision.text,
            "confidence": decision.confidence,
            "signals": decision.signals,
        }
    elif deals:
        recommendation = {
            "action": "watch",
            "text": f"为你找到 {len(deals)} 个航班，最低价 ¥{min(prices)}。" if prices else f"为你找到 {len(deals)} 个航班。",
            "confidence": "medium",
            "signals": [],
        }
    elif search_result:
        recommendation = {
            "action": "watch",
            "text": "暂时没有找到符合条件的航班，可以换个日期或路线再试。",
            "confidence": "low",
            "signals": ["no_deals"],
        }

    resp = FrontendResponse(
        user_id=state.get("request_user_id", ""),
        query=query_summary,
        deals=deals,
        analysis=analysis,
        recommendation=recommendation,
        meta={
            "generated_at": _now(),
            "source": result_source,
            "request_id": str(uuid.uuid4()),
            "result_count": len(deals),
            "fallback_mode": state.get("fallback_triggered", False),
            "missing_slots": state.get("missing_slots", []),
        },
    )

    session_factory = state.get("_session_factory")
    if session_factory and intent and not intent.parse_failed:
        asyncio.create_task(
            _async_memory_writeback(
                user_id=state["request_user_id"],
                message=state.get("request_message", ""),
                intent=intent,
                session_factory=session_factory,
            )
        )

    return {**state, "response": resp}


def _match_score(pref_result, deal_count: int) -> float:
    if not pref_result:
        return 0.0
    if isinstance(pref_result, dict):
        filtered = pref_result.get("filtered", [])
        boosted = pref_result.get("boosted", [])
        return round((len(filtered) + len(boosted)) / max(deal_count, 1), 2)
    return round(
        len([p for p in pref_result.items if p.matched]) / max(deal_count, 1),
        2,
    )


def _extract_prices(search_result, deals: list[dict]) -> list[int]:
    if search_result and not isinstance(search_result, dict):
        return [c.lowest_price for c in search_result.candidates]
    prices: list[int] = []
    for deal in deals:
        price = deal.get("price") or deal.get("lowest_price")
        if isinstance(price, (int, float)):
            prices.append(int(price))
            continue
        nested_prices = deal.get("prices") or []
        for item in nested_prices:
            nested_price = item.get("price") if isinstance(item, dict) else None
            if isinstance(nested_price, (int, float)):
                prices.append(int(nested_price))
    return prices


async def _async_memory_writeback(user_id, message, intent, session_factory):
    try:
        from backend.services.memory_learner import (
            learn_from_query_history,
            learn_from_search,
        )

        await learn_from_search(user_id, intent.model_dump(), session_factory)
        await learn_from_query_history(user_id, session_factory)
    except Exception:
        pass
