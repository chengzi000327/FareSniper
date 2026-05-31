from backend.services.recommend_scorer import sort_deals


def test_sort_deals_tolerates_string_and_missing_cost_fields():
    deals = [
        {"flight_no": "A", "price": "600", "tax": None, "baggage_fee": "0"},
        {"flight_no": "B", "price": 400},
    ]

    sorted_deals = sort_deals(deals, [])

    assert [d["flight_no"] for d in sorted_deals] == ["B", "A"]
    assert all(d["recommend_score"] for d in sorted_deals)
