import pytest

from backend.application.contracts.decision import DecisionResult, RecommendedAction
import backend.application.graph.tools.judge_value as jv


@pytest.mark.asyncio
async def test_judge_value_flags_historical_low(monkeypatch):
    deals = [
        {
            "flight_no": "HU7833",
            "lowest_price": 389,
            "history_avg_90d": 584,
            "depart_date": "2026-06-19",
        }
    ]
    result = await jv.judge_value.ainvoke({"deals": deals, "pref": {}})
    assert isinstance(result, DecisionResult)
    assert "历史低价" in result.signals
    assert result.action in {RecommendedAction.buy_now, RecommendedAction.watch}
    assert result.text


@pytest.mark.asyncio
async def test_judge_value_neutral_when_no_deals():
    result = await jv.judge_value.ainvoke({"deals": [], "pref": {}})
    assert result.action == RecommendedAction.watch
    assert result.signals == []
