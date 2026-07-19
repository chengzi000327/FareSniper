from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from backend.application.services.grounded_response import (
    build_response_facts,
    render_flight_markdown,
    validate_optional_prose,
)


def _deal(
    flight_no: str,
    price: int | None,
    *,
    depart_time: str = "08:00",
    arrive_time: str = "10:00",
    freshness: str = "fresh",
    prices: list[dict] | None = None,
) -> dict:
    return {
        "flight_no": flight_no,
        "platform": "飞猪",
        "depart_time": depart_time,
        "arrive_time": arrive_time,
        "price": price,
        "currency": "CNY",
        "data_freshness": freshness,
        "prices": prices or [],
    }


def test_build_response_facts_freezes_an_ordered_copy():
    deals = [_deal("JD5121", 650), _deal("JD5577", 700)]

    facts = build_response_facts(deals, budget=500)
    deals[0]["flight_no"] = "MUTATED"
    deals.reverse()

    assert isinstance(facts.rows, tuple)
    assert [row.flight_no for row in facts.rows] == ["JD5121", "JD5577"]
    assert facts.best_deal is facts.rows[0]
    assert facts.minimum_display_price == 650
    assert facts.within_budget is False
    with pytest.raises(FrozenInstanceError):
        facts.budget = 600


def test_markdown_preserves_first_deal_and_uses_stale_display_price():
    deals = [
        _deal("JD5121", 650, depart_time="08:00", arrive_time="10:00"),
        _deal(
            "JD5577",
            620,
            depart_time="11:00",
            arrive_time="13:20",
            freshness="stale",
            prices=[
                {
                    "id": "ctrip-JD5577-20260720",
                    "price": 620,
                    "currency": "CNY",
                    "price_status": "stale",
                    "provider_status": "stale",
                    "data_freshness": "stale",
                }
            ],
        ),
    ]
    deals[1]["winning_price_id"] = "ctrip-JD5577-20260720"

    markdown = render_flight_markdown(build_response_facts(deals, budget=500))
    first_row = "| JD5121 | 飞猪 | 08:00 | 10:00 | ¥650 |"
    second_row = "| JD5577 | 飞猪 | 11:00 | 13:20 | ¥620 |"

    assert markdown.index(first_row) < markdown.index(second_row)
    assert "平台展示价最低：¥620" in markdown
    assert "推荐优先查看 JD5121" in markdown
    assert "价格可能已更新，以预订页为准" in markdown
    assert "可设置 ¥500 价格提醒" in markdown


def test_display_price_uses_exact_winning_row_not_cheaper_nested_inventory():
    deal = _deal(
        "JD5121",
        550,
        freshness="fresh",
        prices=[
            {
                "id": "flyai-JD5121-20260720",
                "name": "飞猪",
                "price": 550,
                "currency": "CNY",
                "lowest": True,
                "price_status": "priced",
                "provider_status": "success",
                "data_provider": "flyai",
                "data_freshness": "fresh",
            },
            {
                "id": "ctrip-JD5121-20260720",
                "name": "携程",
                "price": 500,
                "currency": "CNY",
                "lowest": False,
                "price_status": "priced",
                "provider_status": "success",
                "data_provider": "ctrip_snapshot",
                "data_freshness": "fresh",
            },
            {
                "id": "stale-JD5121-20260720",
                "name": "过期平台",
                "price": 400,
                "currency": "CNY",
                "price_status": "stale",
                "provider_status": "stale",
                "data_provider": "serpapi_google_flights",
                "data_freshness": "stale",
            },
        ],
    )
    deal.update(
        {
            "lowest_price": 550,
            "total_price": 550,
            "winning_price_id": "flyai-JD5121-20260720",
        }
    )

    facts = build_response_facts([deal], budget=525)

    assert facts.rows[0].display_price == 550
    assert facts.minimum_display_price == 550
    assert facts.within_budget is False
    assert facts.has_stale_prices is False
    assert "平台展示价最低：¥550" in render_flight_markdown(facts)


def test_winning_row_must_match_card_headline_and_currency():
    deal = _deal(
        "JD5121",
        550,
        prices=[
            {
                "id": "winner",
                "price": 560,
                "currency": "CNY",
                "provider_status": "success",
                "data_freshness": "fresh",
            }
        ],
    )
    deal["winning_price_id"] = "winner"

    with pytest.raises(ValueError, match="winning price"):
        build_response_facts([deal], budget=None)


def test_nested_price_keeps_selected_amount_and_currency_atomic():
    deals = [
        _deal("JD5121", 700, depart_time="08:00", arrive_time="10:00"),
        {
            "flight_no": "JD5577",
            "depart_time": "11:00",
            "arrive_time": "13:20",
            "price": 620,
            "lowest_price": 620,
            "total_price": 620,
            "currency": "CNY",
            "data_freshness": "stale",
            "winning_price_id": "ctrip-JD5577-20260720",
            "prices": [
                {
                    "id": "ctrip-JD5577-20260720",
                    "name": "携程",
                    "price": 620,
                    "currency": "CNY",
                    "price_status": "stale",
                    "provider_status": "stale",
                    "data_provider": "ctrip",
                    "data_freshness": "stale",
                }
            ],
        },
    ]

    facts = build_response_facts(deals, budget=650)
    cards = facts.card_deals()
    markdown = render_flight_markdown(facts)

    assert facts.currency == "CNY"
    assert (facts.rows[1].display_price, facts.rows[1].currency) == (620, "CNY")
    assert facts.minimum_display_price == 620
    assert facts.within_budget is True
    assert "| JD5577 | 携程 | 11:00 | 13:20 | ¥620 |" in markdown
    assert "USD 620" not in markdown
    assert "平台展示价最低：¥620" in markdown
    assert "当前最低平台展示价在预算 ¥650 内" in markdown
    assert "价格可能已更新，以预订页为准" in markdown
    assert cards == deals
    assert [row.flight_no for row in facts.rows] == [
        card["flight_no"] for card in cards
    ]


@pytest.mark.parametrize(
    "text",
    [
        "最低价是 ¥650",
        "价格是 650 元",
        "另一个平台是 USD 80",
        "这些票价很便宜，而且在预算内",
        "建议购买 JD5121",
        "建议选择 08:00 出发",
        "建议选择 2026-07-20 出发",
        "JD-5121 明早起飞，含税且有免费托运行李",
        "符合你的心理价位",
        "明天起飞，不是后天",
        "票价不含税",
        "可以免费托运行李",
        "预算充足，但这不是最低价",
    ],
)
def test_optional_prose_rejects_factual_fare_tokens(text: str):
    facts = build_response_facts([_deal("JD5121", 650)], budget=None)

    assert validate_optional_prose(text, facts) is None


def test_optional_prose_conservatively_rejects_even_non_factual_text():
    facts = build_response_facts([_deal("JD5121", 650)], budget=None)

    assert validate_optional_prose("希望这些结果能帮你做决定。", facts) is None
