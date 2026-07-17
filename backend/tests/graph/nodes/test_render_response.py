from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage

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
    assert out["response"].meta["source"] == "none"


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


@pytest.mark.asyncio
async def test_render_accepts_react_preference_dict():
    state = {
        "search_result": {"deals": [{"flight_no": "MU5137", "price": 480}]},
        "pref_result": {
            "filtered": [{"flight_no": "MU5137", "reasons": ["符合预算"]}],
            "boosted": [],
        },
        "decision": None,
        "request_user_id": "u1",
    }
    out = await render_response(state)
    rsp = out["response"]
    assert rsp.analysis["match_score"] == 1.0
    assert "符合预算" in rsp.analysis["matched_preferences"]


@pytest.mark.asyncio
async def test_final_ai_text_becomes_recommendation_text():
    state = {
        "request_user_id": "u1",
        "messages": [HumanMessage(content="你好"), AIMessage(content="我是 FareSniper，告诉我出发地和目的地吧。")],
    }
    out = await render_response(state)
    assert out["response"].recommendation["text"] == "我是 FareSniper，告诉我出发地和目的地吧。"


@pytest.mark.asyncio
async def test_last_ai_text_skips_tool_call_messages():
    from langchain_core.messages import AIMessage, HumanMessage
    tool_call_ai = AIMessage(content="", tool_calls=[{"name": "search_flights", "args": {}, "id": "1"}])
    text_ai = AIMessage(content="给你找到了北京到上海的航班。")
    state = {
        "request_user_id": "u1",
        # reverse-scan hits tool_call_ai first (continue), then finds text_ai
        "messages": [HumanMessage(content="查机票"), text_ai, tool_call_ai],
    }
    out = await render_response(state)
    assert out["response"].recommendation["text"] == "给你找到了北京到上海的航班。"


@pytest.mark.asyncio
async def test_deals_get_recommend_score_and_sorted_by_total():
    state = {
        "request_user_id": "u1",
        "search_result": {
            "deals": [
                {
                    "flight_no": "A",
                    "price": 600,
                    "tax": 0,
                    "baggage_fee": 0,
                    "stops": 0,
                    "history_avg_90d": 700,
                },
                {
                    "flight_no": "B",
                    "price": 400,
                    "tax": 0,
                    "baggage_fee": 0,
                    "stops": 0,
                    "history_avg_90d": 700,
                },
            ],
            "source": "cache",
        },
    }
    out = await render_response(state)
    deals = out["response"].deals
    assert deals[0]["flight_no"] == "B"
    assert deals[0]["recommend_score"]


@pytest.mark.asyncio
async def test_validation_empty_text_is_not_overwritten_by_ai_message():
    state = {
        "request_user_id": "u1",
        "search_result": {
            "deals": [],
            "source": "validation_error",
            "provider_statuses": {},
            "validation_error": "出发日期必须是未来日期",
        },
        "messages": [AIMessage(content="这段模型文本不能覆盖校验错误")],
    }

    out = await render_response(state)

    assert out["response"].recommendation["text"] == "出发日期必须是未来日期"


@pytest.mark.asyncio
async def test_all_disabled_renders_configuration_copy():
    state = {
        "request_user_id": "u1",
        "search_result": {
            "deals": [],
            "source": "multi_provider",
            "provider_statuses": {"flyai": "disabled", "serpapi": "disabled"},
        },
        "messages": [AIMessage(content="模型兜底文本")],
    }

    out = await render_response(state)

    assert out["response"].recommendation["text"] == (
        "机票数据源尚未配置，请联系管理员完成配置。"
    )


@pytest.mark.asyncio
async def test_all_empty_renders_no_inventory_copy():
    state = {
        "request_user_id": "u1",
        "search_result": {
            "deals": [],
            "source": "multi_provider",
            "provider_statuses": {"flyai": "empty", "ctrip": "empty"},
        },
    }

    out = await render_response(state)

    assert out["response"].recommendation["text"] == (
        "当前日期和航线暂无可售结果，可以换个日期再试。"
    )


@pytest.mark.asyncio
async def test_all_failed_renders_temporary_failure_copy():
    state = {
        "request_user_id": "u1",
        "search_result": {
            "deals": [],
            "source": "multi_provider",
            "provider_statuses": {
                "flyai": "error",
                "ctrip": "timeout",
                "serpapi": "disabled",
            },
        },
        "messages": [AIMessage(content="模型兜底文本")],
    }

    out = await render_response(state)

    assert out["response"].recommendation["text"] == (
        "机票数据暂时不可用，请稍后重试。"
    )


@pytest.mark.asyncio
async def test_mixed_empty_statuses_render_generic_copy():
    state = {
        "request_user_id": "u1",
        "search_result": {
            "deals": [],
            "source": "multi_provider",
            "provider_statuses": {"flyai": "empty", "ctrip": "queued"},
        },
    }

    out = await render_response(state)

    assert out["response"].recommendation["text"] == (
        "暂时没有找到符合条件的航班，可以换个日期或路线再试。"
    )


@pytest.mark.asyncio
async def test_multi_provider_deal_order_is_preserved_when_price_is_missing():
    state = {
        "request_user_id": "u1",
        "search_result": {
            "source": "multi_provider",
            "deals": [
                {"flight_no": "REALTIME", "price": 500, "stops": 0},
                {
                    "flight_no": "SNAPSHOT_ONLY",
                    "price": None,
                    "stops": 0,
                    "prices": [{"name": "携程", "price": 100}],
                },
            ],
        },
    }

    out = await render_response(state)

    assert [deal["flight_no"] for deal in out["response"].deals] == [
        "REALTIME",
        "SNAPSHOT_ONLY",
    ]
    assert all(deal["recommend_score"] for deal in out["response"].deals)
