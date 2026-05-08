from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage

from backend.application.contracts.decision import DecisionResult, FrontendResponse, RecommendedAction
from backend.application.contracts.search import FlightSearchResult
from backend.application.graph.nodes.render_response import render_response


def _make_decision():
    return DecisionResult(
        action=RecommendedAction.buy_now,
        text="历史低价，建议尽快下单",
        signals=["历史低价", "符合心理价位"],
        confidence="high",
    )


@pytest.mark.asyncio
async def test_render_combines_deals_and_decision():
    state = {
        "search_result": {"deals": [{"flight_no": "MU5137", "price": 480}]},
        "decision": _make_decision(),
        "request_user_id": "u1",
    }
    out = await render_response(state)
    rsp = out["response"]
    assert isinstance(rsp, FrontendResponse)
    assert len(rsp.deals) == 1
    assert rsp.recommendation.get("action") == "buy_now"
    assert "历史低价" in rsp.recommendation.get("text", "")


@pytest.mark.asyncio
async def test_render_empty_when_no_search_result():
    state = {
        "search_result": None,
        "decision": None,
        "request_user_id": "u1",
    }
    out = await render_response(state)
    assert out["response"].deals == []


@pytest.mark.asyncio
async def test_render_carries_fallback_in_meta():
    """fallback_triggered=True means meta.fallback_mode is set."""
    payload = {"ui": "modal", "fields": ["origin", "destination"], "reason": "clarify_exceeded"}
    state = {
        "fallback_triggered": True,
        "messages": [AIMessage(content=json.dumps(payload))],
        "search_result": None,
        "decision": None,
        "request_user_id": "u1",
    }
    out = await render_response(state)
    rsp = out["response"]
    assert rsp.meta.get("fallback_mode") is True
    assert rsp.deals == []
