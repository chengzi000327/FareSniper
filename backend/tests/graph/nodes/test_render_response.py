from __future__ import annotations

import json

import pytest
from langchain_core.messages import AIMessage, HumanMessage

from backend.application.contracts.decision import DecisionResult, FrontendResponse, RecommendedAction
from backend.application.contracts.intent import (
    DateWindow,
    LocationRef,
    NormalizedIntent,
    SlotBundle,
)
from backend.application.contracts.search import FlightSearchResult
from backend.application.graph.nodes.render_response import render_response


def _make_decision():
    return DecisionResult(
        action=RecommendedAction.buy_now,
        text="历史低价，建议尽快下单",
        signals=["历史低价", "符合心理价位"],
        confidence="high",
    )


def deal(flight_no: str, price: int) -> dict:
    return {"flight_no": flight_no, "price": price, "currency": "CNY"}


@pytest.mark.asyncio
async def test_ai_price_cannot_disagree_with_card():
    state = {
        "search_result": {"deals": [deal("JD5121", 650), deal("JD5577", 700)]},
        "messages": [AIMessage(content="最低价是 ¥700，建议购买 JD5577")],
        "accumulated_slots": SlotBundle(budget=500),
        "request_user_id": "u1",
    }
    response = (await render_response(state))["response"]
    assert response.deals[0]["price"] == 650
    assert "¥650" in response.recommendation["text"]
    assert "最低价是 ¥700" not in response.recommendation["text"]
    assert "JD5121" in response.recommendation["text"]


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
    assert rsp.recommendation.get("action") == "watch"
    assert rsp.recommendation.get("confidence") == "medium"
    assert rsp.recommendation.get("signals") == []
    assert "MU5137" in rsp.recommendation.get("text", "")
    assert "¥480" in rsp.recommendation.get("text", "")
    assert "历史低价" not in rsp.recommendation.get("text", "")


@pytest.mark.asyncio
async def test_chat_history_uses_the_grounded_final_snapshot(monkeypatch):
    persisted: dict[str, str] = {}

    async def capture_history(**kwargs):
        persisted["assistant_text"] = kwargs["assistant_text"]

    monkeypatch.setattr(
        "backend.application.graph.nodes.render_response._write_chat_history",
        capture_history,
    )
    state = {
        "search_result": {"deals": [deal("JD5121", 650), deal("JD5577", 700)]},
        "messages": [AIMessage(content="最低价是 ¥700，建议购买 JD5577")],
        "decision": _make_decision(),
        "request_user_id": "u1",
        "request_session_id": "s1",
        "_session_factory": object(),
    }

    response = (await render_response(state))["response"]

    assert persisted["assistant_text"] == response.recommendation["text"]
    assert "¥650" in persisted["assistant_text"]
    assert "最低价是 ¥700" not in persisted["assistant_text"]
    assert "| JD5577 |" in persisted["assistant_text"]
    assert response.recommendation["signals"] == []


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
async def test_deal_response_does_not_copy_pre_snapshot_preference_claims():
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
    assert rsp.analysis["match_score"] == 0.0
    assert rsp.analysis["matched_preferences"] == []


@pytest.mark.asyncio
async def test_deal_response_grounds_all_price_and_budget_fields_in_final_facts():
    intent = NormalizedIntent(
        origin=LocationRef(city="北京", iata_code="PEK"),
        destination=LocationRef(city="上海", iata_code="SHA"),
        date_window=DateWindow(start_date="2026-07-20", end_date="2026-07-20"),
        budget_cny=900,
        raw_text="北京到上海，预算900",
    )
    state = {
        "request_user_id": "u1",
        "intent": intent,
        "accumulated_slots": SlotBundle(budget=500),
        "search_result": {
            "source": "multi_provider",
            "deals": [
                {
                    "flight_no": "JD5121",
                    "price": 700,
                    "lowest_price": 700,
                    "total_price": 700,
                    "currency": "CNY",
                    "data_freshness": "fresh",
                    "winning_price_id": "fresh-JD5121",
                    "prices": [
                        {
                            "id": "fresh-JD5121",
                            "name": "飞猪",
                            "price": 700,
                            "currency": "CNY",
                            "price_status": "priced",
                            "provider_status": "success",
                            "data_freshness": "fresh",
                        },
                        {
                            "id": "stale-JD5121",
                            "name": "携程",
                            "price": 620,
                            "currency": "CNY",
                            "price_status": "stale",
                            "provider_status": "stale",
                            "data_freshness": "stale",
                        }
                    ],
                },
                deal("JD5577", 800),
            ],
        },
        "decision": _make_decision(),
        "pref_result": {
            "filtered": [{"flight_no": "JD5121", "reasons": ["符合心理价位"]}],
            "boosted": [],
        },
        "messages": [AIMessage(content="符合你的心理价位，最低 ¥680，建议买 JD-5121")],
    }

    response = (await render_response(state))["response"]

    assert response.query["budget"] == 500
    assert response.analysis == {
        "min_price": 700,
        "max_price": 800,
        "avg_price": 750,
        "currency": "CNY",
        "avg_90d": None,
        "lower_than_avg": None,
        "price_spread_pct": None,
        "match_score": 0.0,
        "within_budget": False,
        "matched_preferences": [],
        "budget": 500,
    }
    assert response.recommendation["action"] == "watch"
    assert response.recommendation["confidence"] == "medium"
    assert response.recommendation["signals"] == []
    assert "平台展示价最低：¥700" in response.recommendation["text"]
    assert "可设置 ¥500 价格提醒" in response.recommendation["text"]
    assert "¥680" not in response.recommendation["text"]
    assert "符合你的心理价位" not in response.recommendation["text"]


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


@pytest.mark.asyncio
async def test_final_analysis_does_not_compare_unlike_currencies():
    state = {
        "request_user_id": "u1",
        "search_result": {
            "source": "multi_provider",
            "deals": [
                {
                    "flight_no": "CNY1",
                    "price": 550,
                    "total_price": 550,
                    "currency": "CNY",
                    "stops": 0,
                },
                {
                    "flight_no": "USD1",
                    "price": 80,
                    "total_price": 80,
                    "currency": "USD",
                    "stops": 0,
                },
            ],
        },
    }

    out = await render_response(state)
    response = out["response"]

    assert response.analysis["min_price"] == 550
    assert response.analysis["max_price"] == 550
    assert response.analysis["currency"] == "CNY"
    assert "CNY 550" in response.recommendation["text"]
    assert "¥80" not in response.recommendation["text"]
