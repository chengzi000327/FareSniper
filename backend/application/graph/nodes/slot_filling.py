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
    intent_definition_for,
    missing_required_slots,
    slots_to_intent,
)
from backend.application.services.intent_registry import load_intent_registry
from backend.infrastructure.redis.session_store import save_slots

logger = logging.getLogger("faresniper.graph.slot_filling")


async def fill_intent_slots(state: WorkflowState) -> WorkflowState:
    """Parse intent slots from the latest turn and persist accumulated slots."""
    text = _latest_user_text(state)
    intent_definitions = await load_intent_registry()
    slots = fill_slots(
        text,
        state.get("accumulated_slots"),
        intent_definitions=intent_definitions,
    )
    intent = slots_to_intent(slots, text, intent_definitions)
    missing = missing_required_slots(slots, intent_definitions)
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
        "intent_definitions": intent_definitions,
    }


def route_after_slot_filling(state: WorkflowState) -> str:
    """Route to clarification until all required search slots are present."""
    missing = state.get("missing_slots") or []
    if missing:
        return "clarify_response"
    definition = intent_definition_for(
        state.get("accumulated_slots"),
        state.get("intent_definitions"),
    )
    if definition and definition.handler_name != "search_flights":
        return "dynamic_intent_response"
    if not definition:
        return "dynamic_intent_response"
    return "run_slot_search"


async def slot_clarify_response(state: WorkflowState) -> WorkflowState:
    """Return a single-slot follow-up question and keep partial slots in meta."""
    slots = state.get("accumulated_slots")
    missing = state.get("missing_slots") or missing_required_slots(
        slots,
        state.get("intent_definitions"),
    )
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
            "intent": slots.intent if slots else None,
        },
    )
    return {"messages": [AIMessage(content=question)], "response": response}


async def dynamic_intent_response(state: WorkflowState) -> WorkflowState:
    """Handle dynamic intents that are recognized but do not yet have a runtime handler."""
    slots = state.get("accumulated_slots")
    definition = intent_definition_for(slots, state.get("intent_definitions"))
    text = _dynamic_intent_text(definition.name if definition else None)
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
            "action": definition.handler_name if definition else "recognized_intent",
            "text": text,
            "confidence": "medium",
            "signals": ["dynamic_intent_recognized"],
        },
        meta={
            "source": "dynamic_intent",
            "result_count": 0,
            "fallback_mode": False,
            "missing_slots": [],
            "accumulated_slots": _slot_dict(slots),
            "intent": definition.name if definition else None,
            "handler_name": definition.handler_name if definition else None,
        },
    )
    return {"messages": [AIMessage(content=text)], "response": response}


async def run_slot_search(state: WorkflowState) -> WorkflowState:
    """Execute the flight-search tool from completed accumulated slots."""
    slots = state.get("accumulated_slots")
    missing = missing_required_slots(slots, state.get("intent_definitions"))
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
        "target_price": slots.target_price,
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
        "target_price": slots.target_price,
        "constraints": slots.constraints,
    }


def _dynamic_intent_text(intent_name: str | None) -> str:
    if intent_name == "set_alert":
        return "已识别为低价提醒意图，提醒创建接口还在接入中。"
    if intent_name == "check_preference":
        return "已识别为查看偏好意图，偏好读取接口还在接入中。"
    if intent_name == "update_preference":
        return "已识别为更新偏好意图，偏好写入接口还在接入中。"
    if intent_name in {"chitchat", "smalltalk"}:
        return "我是 FareSniper，你的机票决策助手。你可以直接告诉我出发地、目的地和时间，我会帮你比价、看价格信号，并判断现在值不值得买。"
    return "已识别到新的动态意图，对应处理器还在接入中。"


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
