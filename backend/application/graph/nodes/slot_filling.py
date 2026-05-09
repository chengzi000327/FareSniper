"""Slot-filling nodes for the runtime search graph."""

from __future__ import annotations

import logging

from langchain_core.messages import AIMessage, HumanMessage

from backend.application.contracts.decision import FrontendResponse
from backend.application.graph.state import WorkflowState
from backend.application.graph.tools.search_flights import search_flights
from backend.application.services.intent_slot_filler import (
    build_clarify_question,
    fill_slots,
    missing_required_slots,
    slots_to_intent,
)
from backend.infrastructure.redis.session_store import save_slots

logger = logging.getLogger("faresniper.graph.slot_filling")


async def fill_intent_slots(state: WorkflowState) -> WorkflowState:
    """Parse intent slots from the latest turn and persist accumulated slots."""
    text = _latest_user_text(state)
    slots = fill_slots(text, state.get("accumulated_slots"))
    intent = slots_to_intent(slots, text)
    missing = missing_required_slots(slots)
    session_id = state.get("request_session_id")

    if session_id:
        try:
            await save_slots(session_id, slots)
        except Exception:
            logger.exception("save_slots_failed session_id=%s", session_id)

    await _track_intent(state, intent_complete=not missing, parse_failed=intent.parse_failed)

    logger.info(
        "intent_slots_filled user_id=%s session_id=%s intent=%s origin=%s destination=%s depart_date=%s missing=%s",
        state.get("request_user_id", ""),
        session_id,
        slots.intent,
        slots.origin,
        slots.destination,
        slots.depart_date,
        ",".join(missing),
    )
    return {
        "accumulated_slots": slots,
        "intent": intent,
        "missing_slots": missing,
    }


def route_after_slot_filling(state: WorkflowState) -> str:
    """Route to clarification until all required search slots are present."""
    missing = state.get("missing_slots") or []
    if missing:
        return "clarify_response"
    return "run_slot_search"


async def slot_clarify_response(state: WorkflowState) -> WorkflowState:
    """Return a single-slot follow-up question and keep partial slots in meta."""
    slots = state.get("accumulated_slots")
    missing = state.get("missing_slots") or missing_required_slots(slots)
    question = build_clarify_question(slots, missing)
    response = FrontendResponse(
        user_id=state.get("request_user_id", ""),
        session_id=state.get("request_session_id"),
        query=_query_from_slots(slots),
        deals=[],
        analysis={
            "min_price": None,
            "max_price": None,
            "avg_price": None,
            "avg_90d": None,
            "lower_than_avg": None,
            "price_spread_pct": None,
            "match_score": 0.0,
            "within_budget": False,
            "matched_preferences": [],
        },
        recommendation={
            "action": "ask_user",
            "text": question,
            "confidence": "high",
            "signals": ["intent_incomplete"],
        },
        meta={
            "source": "slot_filling",
            "result_count": 0,
            "fallback_mode": False,
            "missing_slots": missing,
            "accumulated_slots": _slot_dict(slots),
        },
    )
    return {"messages": [AIMessage(content=question)], "response": response}


async def run_slot_search(state: WorkflowState) -> WorkflowState:
    """Execute the flight-search tool from completed accumulated slots."""
    slots = state.get("accumulated_slots")
    missing = missing_required_slots(slots)
    if not slots or missing:
        return {"missing_slots": missing}

    result = await search_flights.ainvoke(
        {
            "origin": slots.origin,
            "destination": slots.destination,
            "depart_date": slots.depart_date,
        }
    )
    return {
        "search_result": result,
        "fallback_triggered": result.get("source") == "mock_fallback",
    }


def _latest_user_text(state: WorkflowState) -> str:
    if state.get("request_message"):
        return str(state["request_message"])
    for message in reversed(state.get("messages", [])):
        if isinstance(message, HumanMessage) or getattr(message, "type", "") == "human":
            return str(message.content)
    return ""


def _query_from_slots(slots) -> dict | None:
    if not slots:
        return None
    return {
        "raw_text": "",
        "normalized_text": "",
        "origin_city": slots.origin or "",
        "origin_code": "",
        "destination_city": slots.destination or "",
        "destination_code": "",
        "date_start": slots.depart_date or "",
        "date_end": slots.return_date or "",
        "budget": slots.budget,
    }


def _slot_dict(slots) -> dict:
    if not slots:
        return {}
    return {
        "intent": slots.intent,
        "origin": slots.origin,
        "destination": slots.destination,
        "depart_date": slots.depart_date,
        "return_date": slots.return_date,
        "budget": slots.budget,
        "constraints": slots.constraints,
    }


async def _track_intent(
    state: WorkflowState, *, intent_complete: bool, parse_failed: bool
) -> None:
    try:
        from backend.analytics.events import EventName
        from backend.analytics.track import track

        await track(
            EventName.INTENT_PARSED,
            user_id=state.get("request_user_id", ""),
            payload={"intent_complete": intent_complete, "parse_failed": parse_failed},
        )
    except Exception:
        pass
