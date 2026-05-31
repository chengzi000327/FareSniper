import pytest

from backend.infrastructure.db.flight_snapshot_repo import upsert_flights, read_deals


@pytest.mark.asyncio
async def test_upsert_then_read(seeded_pg):
    flights = [{
        "flight_no": "MU5106", "airline": "东方航空",
        "origin_code": "BJS", "destination_code": "SHA", "depart_date": "2026-05-01",
        "dep_time": "08:00", "arr_time": "10:00", "duration": "2h00m", "stops": 0,
        "lowest_price": 280, "history_avg_90d": 420, "history_low_90d": 240,
        "prices": [
            {"platform": "携程", "price": 280, "lowest": True, "url": "ctrip://x"},
            {"platform": "去哪儿", "price": 299, "lowest": False, "url": "qunar://x"},
        ],
    }]
    await upsert_flights(flights)
    deals = await read_deals(origin_code="BJS", destination_code="SHA", depart_date="2026-05-01")
    assert len(deals) == 1
    assert deals[0]["flight_no"] == "MU5106"
    assert deals[0]["lowest_price"] == 280
    assert len(deals[0]["prices"]) == 2
    assert deals[0]["data_freshness"] == "fresh"


@pytest.mark.asyncio
async def test_read_miss_returns_empty(seeded_pg):
    assert await read_deals(origin_code="BJS", destination_code="XIY", depart_date="2026-05-01") == []


@pytest.mark.asyncio
async def test_upsert_is_idempotent_on_dedup_key(seeded_pg):
    f = {
        "flight_no": "MU5106", "airline": "东方航空", "origin_code": "BJS", "destination_code": "SHA",
        "depart_date": "2026-05-01", "dep_time": "08:00", "arr_time": "10:00", "duration": "2h",
        "stops": 0, "lowest_price": 280, "history_avg_90d": None, "history_low_90d": None,
        "prices": [{"platform": "携程", "price": 280, "lowest": True, "url": ""}],
    }
    await upsert_flights([f])
    f2 = dict(f, lowest_price=250, prices=[{"platform": "携程", "price": 250, "lowest": True, "url": ""}])
    await upsert_flights([f2])
    deals = await read_deals(origin_code="BJS", destination_code="SHA", depart_date="2026-05-01")
    assert len(deals) == 1  # same dedup key → one row, updated
    assert deals[0]["lowest_price"] == 250
    assert len(deals[0]["prices"]) == 1  # old platform prices replaced, not duplicated
