from backend.services.recommend_scorer import calc_recommend_score, sort_deals


def test_sort_deals_tolerates_string_and_missing_cost_fields():
    deals = [
        {"flight_no": "A", "price": "600", "tax": None, "baggage_fee": "0"},
        {"flight_no": "B", "price": 400},
    ]

    sorted_deals = sort_deals(deals, [])

    assert [d["flight_no"] for d in sorted_deals] == ["B", "A"]
    assert all(d["recommend_score"] for d in sorted_deals)


def test_unknown_baggage_fee_does_not_receive_zero_fee_bonus():
    unknown = {"price": 500, "stops": 1, "baggage_fee": None}
    explicitly_free = {"price": 500, "stops": 1, "baggage_fee": 0}

    assert calc_recommend_score(unknown, None) == "0.0"
    assert calc_recommend_score(explicitly_free, None) == "1.0"
