"""Render graph state into the frontend response contract."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime, timezone

logger = logging.getLogger("faresniper.graph.render_response")

from backend.application.contracts.decision import FrontendResponse
from backend.application.graph.state import WorkflowState
from backend.application.services.grounded_response import (
    ResponseFacts,
    build_response_facts,
    render_flight_markdown,
    validate_optional_prose,
)


_AUTHORITATIVE_QUERY_FIELDS = (
    "origin_city",
    "origin_code",
    "origin_airport_ids",
    "origin_airport_scope",
    "destination_city",
    "destination_code",
    "destination_airport_ids",
    "destination_airport_scope",
    "date_start",
    "date_end",
)


def _now() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def render_response(state: WorkflowState) -> WorkflowState:
    search_result = state.get("search_result")
    decision = state.get("decision")
    intent = state.get("intent")
    pref_result = state.get("pref_result")

    deals = []
    result_source = "none"
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
                deal["platform"] = ""
                deal["origin_city"] = c.origin_city or (
                    intent.origin.city if intent and intent.origin else ""
                )
                deal["destination_city"] = c.destination_city or (
                    intent.destination.city if intent and intent.destination else ""
                )
                deal["depart_time"] = c.depart_time
                deal["arrive_time"] = c.arrive_time
                deal["price"] = None
                deal["lowest_price"] = None
                deal["base_price"] = None
                deal["total_price"] = None
                deal["currency"] = "CNY"
                deal["winning_price_id"] = None
                deal["data_freshness"] = "unknown"
                deal["booking_url"] = None
                deal["h5_fallback_url"] = None
                deal["prices"] = [
                    {
                        "id": f"mock-{c.flight_no}-{index}",
                        "name": price.platform,
                        "price": price.price,
                        "currency": "CNY",
                        "lowest": False,
                        "price_status": "stale",
                        "provider_status": "disabled",
                        "url": None,
                        "data_provider": "mock_reference",
                        "data_freshness": "unknown",
                    }
                    for index, price in enumerate(c.prices)
                ]
                deals.append(deal)

    if deals:
        from backend.services.recommend_scorer import (
            calc_recommend_score,
            sort_deals,
        )

        pref_results = []
        if isinstance(pref_result, dict):
            pref_results = pref_result.get("filtered", []) + pref_result.get("boosted", [])
        if result_source == "multi_provider":
            pref_map = {
                item.get("flight_no", ""): item
                for item in pref_results
                if item.get("flight_no")
            }
            for deal in deals:
                deal["recommend_score"] = calc_recommend_score(
                    deal, pref_map.get(deal.get("flight_no", ""))
                )
        else:
            deals = sort_deals(deals, pref_results)
        for deal in deals:
            if (
                (
                    "winning_price_id" in deal
                    and deal.get("winning_price_id") is None
                )
                or (
                    "data_freshness" in deal
                    and deal.get("data_freshness") != "fresh"
                )
            ):
                deal["recommend_score"] = None

    response_facts: ResponseFacts | None = None
    if deals:
        response_facts = build_response_facts(deals, _response_budget(state, intent))
        deals = response_facts.card_deals()

    primary_currency = (
        response_facts.currency if response_facts else _primary_currency(deals)
    )
    prices = (
        [
            row.display_price
            for row in response_facts.rows
            if row.currency == response_facts.currency
            and row.display_price is not None
        ]
        if response_facts
        else _extract_prices(search_result, deals, primary_currency)
    )
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

    if response_facts is not None:
        analysis = {
            "min_price": min(prices) if prices else None,
            "max_price": max(prices) if prices else None,
            "avg_price": int(sum(prices) / len(prices)) if prices else None,
            "currency": response_facts.currency,
            "avg_90d": None,
            "lower_than_avg": None,
            "price_spread_pct": None,
            "match_score": 0.0,
            "within_budget": response_facts.within_budget,
            "matched_preferences": [],
            "budget": response_facts.budget,
        }
    else:
        analysis = {
            "min_price": min(prices) if prices else None,
            "max_price": max(prices) if prices else None,
            "avg_price": int(sum(prices) / len(prices)) if prices else None,
            "currency": primary_currency,
            "avg_90d": int(sum(avg_90d_vals) / len(avg_90d_vals)) if avg_90d_vals else None,
            "lower_than_avg": lower_than_avg,
            "price_spread_pct": None,
            "match_score": _match_score(pref_result, len(deals)),
            "within_budget": bool(
                decision and "符合心理价位" in decision.signals
            ),
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
            "budget": response_facts.budget if response_facts else intent.budget_cny,
        }
    if (
        isinstance(search_result, dict)
        and isinstance(search_result.get("query"), dict)
    ):
        snapshot_query = search_result["query"]
        authoritative_query = {
            field: snapshot_query[field]
            for field in _AUTHORITATIVE_QUERY_FIELDS
            if field in snapshot_query
        }
        if query_summary is None:
            query_summary = authoritative_query
        else:
            query_summary.update(authoritative_query)

    empty_search_text = (
        _empty_search_text(search_result)
        if isinstance(search_result, dict) and not deals
        else None
    )
    final_text = _last_ai_text(state)
    recommendation = {}
    if response_facts is not None:
        grounded_text = render_flight_markdown(response_facts)
        optional_prose = validate_optional_prose(final_text, response_facts)
        if optional_prose:
            grounded_text = f"{grounded_text}\n\n{optional_prose}"
        recommendation = {
            "action": "watch",
            "text": grounded_text,
            "confidence": "medium",
            "signals": [],
        }
    elif empty_search_text is not None:
        recommendation = {
            "action": "watch",
            "text": empty_search_text,
            "confidence": "low",
            "signals": ["no_deals"],
        }
    elif decision:
        recommendation = {
            "action": decision.action.value,
            "text": decision.text,
            "confidence": decision.confidence,
            "signals": decision.signals,
        }
    elif search_result:
        recommendation = {
            "action": "watch",
            "text": "暂时没有找到符合条件的航班，可以换个日期或路线再试。",
            "confidence": "low",
            "signals": ["no_deals"],
        }

    if final_text and response_facts is None and empty_search_text is None:
        if recommendation:
            recommendation["text"] = final_text
        else:
            recommendation = {
                "action": "watch",
                "text": final_text,
                "confidence": "medium",
                "signals": [],
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
    user_id = state.get("request_user_id", "")
    session_id = state.get("request_session_id", "")
    user_message = state.get("request_message", "")
    assistant_text = resp.recommendation.get("text", "") if isinstance(resp.recommendation, dict) else ""

    logger.info(
        "memory_writeback_check session_factory=%s session_id=%s user_id=%s "
        "user_message_len=%d assistant_text_len=%d",
        "present" if session_factory else "NONE",
        session_id or "NONE",
        user_id or "NONE",
        len(user_message),
        len(assistant_text),
    )

    if session_factory:
        await _write_chat_history(
            session_factory=session_factory,
            session_id=session_id,
            user_id=user_id,
            user_message=user_message,
            assistant_text=assistant_text,
        )
        # 偏好提取：不依赖 intent（ReAct 路径 intent 常为 None），直接从用户消息提取
        if user_id and user_message:
            try:
                from backend.services.preference_extractor import learn_preferences

                await learn_preferences(user_id, user_message, session_factory)
            except Exception:
                logger.warning("learn_preferences_failed user_id=%s", user_id, exc_info=True)
        # 行为推断学习（仅在拿到结构化 intent 时补充）
        if intent and not intent.parse_failed:
            await _async_memory_writeback(
                user_id=user_id,
                message=user_message,
                intent=intent,
                session_factory=session_factory,
            )
    else:
        logger.warning(
            "memory_writeback_skipped reason=no_session_factory "
            "user_id=%s session_id=%s",
            user_id,
            session_id,
        )

    return {**state, "response": resp}


def _empty_search_text(search_result: dict) -> str:
    validation = search_result.get("validation_error")
    if validation:
        return validation
    statuses = list((search_result.get("provider_statuses") or {}).values())
    if statuses and all(status == "disabled" for status in statuses):
        return "机票数据源尚未配置，请联系管理员完成配置。"
    if statuses and all(status == "empty" for status in statuses):
        return "当前日期和航线暂无可售结果，可以换个日期再试。"
    if statuses and all(
        status in {"error", "timeout", "disabled"} for status in statuses
    ):
        return "机票数据暂时不可用，请稍后重试。"
    return "暂时没有找到符合条件的航班，可以换个日期或路线再试。"


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


def _response_budget(state, intent) -> int | None:
    slots = state.get("accumulated_slots")
    if isinstance(slots, dict):
        budget = slots.get("budget")
    else:
        budget = getattr(slots, "budget", None)
    if isinstance(budget, int) and not isinstance(budget, bool):
        return budget
    intent_budget = getattr(intent, "budget_cny", None)
    return (
        intent_budget
        if isinstance(intent_budget, int) and not isinstance(intent_budget, bool)
        else None
    )


def _primary_currency(deals: list[dict]) -> str | None:
    for deal in deals:
        currency = deal.get("currency")
        if isinstance(currency, str) and len(currency.strip()) == 3:
            return currency.strip().upper()
    return None


def _extract_prices(
    search_result, deals: list[dict], primary_currency: str | None
) -> list[int]:
    if search_result and not isinstance(search_result, dict):
        return [c.lowest_price for c in search_result.candidates]
    prices: list[int] = []
    for deal in deals:
        deal_currency = deal.get("currency")
        if (
            primary_currency
            and isinstance(deal_currency, str)
            and deal_currency.upper() != primary_currency
        ):
            continue
        price = deal.get("price")
        if not isinstance(price, (int, float)):
            price = deal.get("lowest_price")
        if isinstance(price, (int, float)):
            prices.append(int(price))
            continue
        nested_prices = deal.get("prices") or []
        for item in nested_prices:
            if (
                primary_currency
                and isinstance(item, dict)
                and isinstance(item.get("currency"), str)
                and item["currency"].upper() != primary_currency
            ):
                continue
            nested_price = item.get("price") if isinstance(item, dict) else None
            if isinstance(nested_price, (int, float)):
                prices.append(int(nested_price))
    return prices


def _last_ai_text(state) -> str | None:
    """取最近一条「非工具调用」的 AIMessage 文本，作为 ReAct 最终自然语言回复。"""
    for m in reversed(state.get("messages") or []):
        is_ai = getattr(m, "type", "") == "ai" or m.__class__.__name__ == "AIMessage"
        if not is_ai:
            continue
        if getattr(m, "tool_calls", None):
            continue
        content = getattr(m, "content", "")
        return content.strip() if isinstance(content, str) and content.strip() else None
    return None


async def _write_chat_history(
    session_factory, session_id: str, user_id: str, user_message: str, assistant_text: str
) -> None:
    """写 user + assistant 两条 chat_history 记录，供下轮记忆读取。"""
    if not session_id or not user_id or not (user_message or assistant_text):
        logger.warning(
            "chat_history_skipped reason=missing_field session_id=%s user_id=%s",
            session_id or "NONE", user_id or "NONE",
        )
        return
    try:
        from backend.db.models import ChatHistory

        async with session_factory() as db:
            if user_message:
                db.add(ChatHistory(session_id=session_id, user_id=user_id, role="user", content=user_message))
            if assistant_text:
                db.add(ChatHistory(session_id=session_id, user_id=user_id, role="assistant", content=assistant_text))
            await db.commit()
        logger.info(
            "chat_history_written session_id=%s user_id=%s", session_id, user_id
        )
    except Exception:
        logger.exception(
            "chat_history_write_failed session_id=%s user_id=%s", session_id, user_id
        )


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
