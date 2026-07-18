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
            None,
            depart_time="11:00",
            arrive_time="13:20",
            freshness="stale",
            prices=[
                {
                    "price": 620,
                    "currency": "CNY",
                    "data_freshness": "stale",
                }
            ],
        ),
    ]

    markdown = render_flight_markdown(build_response_facts(deals, budget=500))
    first_row = "| JD5121 | 08:00 | 10:00 | ¥650 |"
    second_row = "| JD5577 | 11:00 | 13:20 | ¥620 |"

    assert markdown.index(first_row) < markdown.index(second_row)
    assert "平台展示价最低：¥620" in markdown
    assert "推荐优先查看 JD5121" in markdown
    assert "价格可能已更新，以预订页为准" in markdown
    assert "可设置 ¥500 价格提醒" in markdown


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
    ],
)
def test_optional_prose_rejects_factual_fare_tokens(text: str):
    facts = build_response_facts([_deal("JD5121", 650)], budget=None)

    assert validate_optional_prose(text, facts) is None


def test_optional_prose_accepts_non_factual_chitchat():
    facts = build_response_facts([_deal("JD5121", 650)], budget=None)

    assert validate_optional_prose("希望这些结果能帮你做决定。", facts) == (
        "希望这些结果能帮你做决定。"
    )
