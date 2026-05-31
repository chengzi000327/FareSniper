from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from backend.application.contracts.decision import DecisionResult, RecommendedAction
from backend.config import get_settings
from backend.infrastructure.llm.models import build_chat_model
from backend.services.holiday import is_holiday
from backend.services.value_judge import ValueJudge


def _aggregate(per_flight: list[dict[str, Any]]) -> DecisionResult:
    if not per_flight:
        return DecisionResult(
            action=RecommendedAction.watch,
            confidence="low",
            text="价格正常，可继续关注",
            signals=[],
        )

    best = per_flight[0]
    signals = list(best.get("signals", []))
    advice = best.get("advice") or "价格正常，可继续关注"
    if "历史低价" in signals:
        action = RecommendedAction.buy_now
        confidence = "high"
    elif signals:
        action = RecommendedAction.watch
        confidence = "medium"
    else:
        action = RecommendedAction.watch
        confidence = "low"
    return DecisionResult(
        action=action,
        confidence=confidence,
        text=advice,
        signals=signals,
    )


def _price(deal: dict[str, Any]) -> int | float:
    value = deal.get("lowest_price", deal.get("price", 0))
    return value if isinstance(value, (int, float)) else 0


def _preference_results(
    deals: list[dict[str, Any]],
    pref: dict[str, Any],
) -> list[dict[str, Any]]:
    budget = pref.get("budget") or pref.get("budget_cny") or pref.get("target_price")
    results: list[dict[str, Any]] = []
    for deal in deals:
        flight_no = deal.get("flight_no", deal.get("id", ""))
        in_budget = bool(budget and _price(deal) <= budget)
        results.append(
            {
                "flight_no": flight_no,
                "matched": in_budget,
                "reasons": ["在你的心理价位以内"] if in_budget else [],
            }
        )
    return results


@tool
async def judge_value(
    deals: list[dict[str, Any]] | None = None,
    pref: dict[str, Any] | None = None,
) -> DecisionResult:
    """综合价格、历史均价、节假日与偏好，输出值得买信号与一句话建议。"""
    deals = deals or []
    if not deals:
        return DecisionResult(
            action=RecommendedAction.watch,
            confidence="low",
            text="价格正常，可继续关注",
            signals=[],
        )

    is_holiday_map = {
        deal.get("depart_date", ""): is_holiday(deal.get("depart_date", ""))
        for deal in deals
    }
    pref_results = _preference_results(deals, pref or {})
    judge = ValueJudge(
        llm_client=build_chat_model(role="judge"),
        model=get_settings().model_judge,
    )
    per_flight = await judge.judge(deals, pref_results, is_holiday_map)
    return _aggregate(per_flight)
