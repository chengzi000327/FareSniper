"""Decision synthesis node."""

from __future__ import annotations

import json

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field

from backend.application.contracts.decision import (
    DecisionFactor,
    DecisionResult,
    RecommendedAction,
)
from backend.application.graph.state import WorkflowState
from backend.infrastructure.llm.models import get_judge_model

_SYSTEM_PROMPT = """你是机票价值判断助手。

对每张票输出：signals（值得买信号列表）、advice（≤20字建议）。

判断规则：
1. lowest_price < history_avg_90d × 0.85 → 触发"历史低价"
2. preference_matched=true → 触发"符合心理价位"
3. is_holiday=true → advice 可提及节假日，但不写入 signals

返回对象（with_structured_output 模式）：
{{"items":[{{"flight_no":"HU7833","signals":["历史低价"],"advice":"建议现在买，比均价低43%"}}]}}

advice ≤20字。"""

_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", _SYSTEM_PROMPT),
        ("human", "{payload}"),
    ]
)


class _JudgeItem(BaseModel):
    flight_no: str
    signals: list[str] = Field(default_factory=list)
    advice: str = ""


class _JudgeList(BaseModel):
    items: list[_JudgeItem] = Field(default_factory=list)


def _build_chain():
    model = get_judge_model()
    try:
        return _prompt | model.with_structured_output(_JudgeList)
    except Exception:

        class _FallbackParser:
            async def ainvoke(self, inputs):
                return None

        return _FallbackParser()


_judge_chain = _build_chain()


async def synthesize_decision(state: WorkflowState) -> WorkflowState:
    search_result = state.get("search_result")
    pref_result = state.get("pref_result")
    if not search_result or not search_result.candidates:
        decision = DecisionResult(action=RecommendedAction.skip, text="暂无航班数据")
        return {**state, "decision": decision}

    pref_map = {p.flight_no: p for p in (pref_result.items if pref_result else [])}
    payload = []
    for c in search_result.candidates[:5]:
        pref = pref_map.get(c.flight_no)
        payload.append(
            {
                "flight_no": c.flight_no,
                "lowest_price": c.lowest_price,
                "history_avg_90d": c.history_avg_90d,
                "is_holiday": c.is_holiday,
                "preference_matched": pref.matched if pref else False,
            }
        )

    try:
        result = await _judge_chain.ainvoke(
            {"payload": json.dumps(payload, ensure_ascii=False)}
        )
        if result and hasattr(result, "items"):
            judge_items = result.items
        else:
            raise ValueError("judge fallback")
    except Exception:
        from backend.services.value_judge import ValueJudge

        raw_flights = [c.model_dump() for c in search_result.candidates[:5]]
        raw_pref = [p.model_dump() for p in (pref_result.items if pref_result else [])]
        is_holiday_map = {c.depart_date: c.is_holiday for c in search_result.candidates}
        raw_judged = ValueJudge(llm_client=None)._judge_heuristic(
            raw_flights, raw_pref, is_holiday_map
        )
        judge_items = [_JudgeItem(**j) for j in raw_judged]

    judge_map = {j.flight_no: j for j in judge_items}
    for c in search_result.candidates:
        jud = judge_map.get(c.flight_no)
        if jud:
            c.signals = jud.signals
            c.verdict = jud.advice

    best = search_result.candidates[0]
    top_signals = best.signals
    has_hist_low = "历史低价" in top_signals
    within_budget = "符合心理价位" in top_signals
    if has_hist_low and within_budget:
        action, confidence = RecommendedAction.buy_now, "high"
    elif has_hist_low or within_budget:
        action, confidence = RecommendedAction.watch, "medium"
    else:
        action, confidence = RecommendedAction.watch, "low"

    decision = DecisionResult(
        action=action,
        confidence=confidence,
        text=best.verdict if best else "价格正常，可继续关注",
        signals=top_signals,
        decision_factors=[
            DecisionFactor(factor_type=s, summary=s, weight=1.0) for s in top_signals
        ],
        branch_reason=action.value,
    )
    return {**state, "decision": decision}
