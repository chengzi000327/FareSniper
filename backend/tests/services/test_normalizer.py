from backend.data_sources.normalizer import normalize_raw_rows


def test_aggregates_same_flight_across_platforms():
    rows = [
        {"flight_number": "HU7833", "airline": "海南航空", "dep_city": "北京", "arr_city": "三亚",
         "dep_time": "09:30", "arr_time": "14:20", "duration": "4h50m", "transfer_count": 0,
         "price": 410, "date": "2026-05-01", "platform": "飞猪"},
        {"flight_number": "HU7833", "airline": "海南航空", "dep_city": "北京", "arr_city": "三亚",
         "dep_time": "09:30", "arr_time": "14:20", "duration": "4h50m", "transfer_count": 0,
         "price": 389, "date": "2026-05-01", "platform": "携程"},
    ]
    out = normalize_raw_rows(rows)
    assert len(out) == 1
    f = out[0]
    assert f["flight_no"] == "HU7833"
    assert f["stops"] == 0
    assert f["lowest_price"] == 389
    assert {p["platform"] for p in f["prices"]} == {"飞猪", "携程"}
    assert any(p["lowest"] for p in f["prices"] if p["platform"] == "携程")


def test_drops_invalid_price_rows():
    rows = [
        {"flight_number": "MU1", "dep_city": "北京", "arr_city": "上海", "dep_time": "08:00",
         "date": "2026-05-01", "platform": "携程", "price": 0},
        {"flight_number": "MU1", "dep_city": "北京", "arr_city": "上海", "dep_time": "08:00",
         "date": "2026-05-01", "platform": "去哪儿", "price": 260},
    ]
    out = normalize_raw_rows(rows)
    assert len(out) == 1
    assert out[0]["lowest_price"] == 260
    assert len(out[0]["prices"]) == 1


def test_empty_input():
    assert normalize_raw_rows([]) == []
