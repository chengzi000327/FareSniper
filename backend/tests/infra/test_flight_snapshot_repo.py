import asyncio

import pytest

from backend.infrastructure.db.flight_snapshot_repo import (
    read_deals,
    read_deals_latest,
    read_provider_deals,
    upsert_flights,
    upsert_provider_flights,
)


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


@pytest.mark.asyncio
async def test_concurrent_upserts_same_dedup_key_do_not_collide(seeded_pg):
    base = {
        "flight_no": "MU5106",
        "airline": "东方航空",
        "origin_code": "BJS",
        "destination_code": "SHA",
        "depart_date": "2026-05-01",
        "dep_time": "08:00",
        "arr_time": "10:00",
        "duration": "2h",
        "stops": 0,
        "history_avg_90d": None,
        "history_low_90d": None,
    }
    await asyncio.gather(
        upsert_flights(
            [
                dict(
                    base,
                    lowest_price=280,
                    prices=[{"platform": "携程", "price": 280, "lowest": True, "url": ""}],
                )
            ]
        ),
        upsert_flights(
            [
                dict(
                    base,
                    lowest_price=250,
                    prices=[{"platform": "去哪儿", "price": 250, "lowest": True, "url": ""}],
                )
            ]
        ),
    )

    deals = await read_deals(origin_code="BJS", destination_code="SHA", depart_date="2026-05-01")
    assert len(deals) == 1
    assert deals[0]["lowest_price"] in {250, 280}
    assert len(deals[0]["prices"]) == 1


@pytest.mark.asyncio
async def test_provider_upsert_preserves_other_provider_rows(seeded_pg):
    base = {
        "flight_no": "MU5106",
        "airline": "东方航空",
        "origin_code": "BJS",
        "destination_code": "SHA",
        "depart_date": "2099-08-01",
        "dep_time": "08:00",
        "arr_time": "10:00",
        "duration": "120分钟",
        "stops": 0,
    }
    await upsert_provider_flights(
        "ctrip_snapshot",
        [
            {
                **base,
                "prices": [
                    {
                        "platform": "携程",
                        "price": 580,
                        "url": "https://ctrip.test",
                    }
                ],
            }
        ],
        ttl_minutes=75,
    )
    await upsert_provider_flights(
        "legacy",
        [
            {
                **base,
                "prices": [
                    {
                        "platform": "legacy",
                        "price": 600,
                        "url": "https://legacy.test",
                    }
                ],
            }
        ],
        ttl_minutes=60,
    )

    rows, age, stale = await read_provider_deals(
        provider="ctrip_snapshot",
        origin_code="BJS",
        destination_code="SHA",
        depart_date="2099-08-01",
    )
    legacy_rows, _, _ = await read_provider_deals(
        provider="legacy",
        origin_code="BJS",
        destination_code="SHA",
        depart_date="2099-08-01",
    )

    assert len(rows) == 1
    assert rows[0]["prices"][0]["platform"] == "携程"
    assert len(legacy_rows) == 1
    assert legacy_rows[0]["prices"][0]["platform"] == "legacy"
    assert age is not None
    assert stale is False


@pytest.mark.asyncio
async def test_read_provider_deals_marks_expired_rows_stale(seeded_pg):
    await upsert_provider_flights(
        "ctrip_snapshot",
        [
            {
                "flight_no": "MU5106",
                "airline": "东方航空",
                "origin_code": "BJS",
                "destination_code": "SHA",
                "depart_date": "2099-08-01",
                "dep_time": "08:00",
                "arr_time": "10:00",
                "duration": "120分钟",
                "stops": 0,
                "prices": [
                    {
                        "platform": "携程",
                        "price": 580,
                        "url": "https://ctrip.test",
                    }
                ],
            }
        ],
        ttl_minutes=-1,
    )

    rows, age, stale = await read_provider_deals(
        provider="ctrip_snapshot",
        origin_code="BJS",
        destination_code="SHA",
        depart_date="2099-08-01",
    )

    assert len(rows) == 1
    assert age is not None
    assert stale is True


@pytest.mark.asyncio
async def test_legacy_upsert_preserves_ctrip_provider_rows(seeded_pg):
    base = {
        "flight_no": "MU5106",
        "airline": "东方航空",
        "origin_code": "BJS",
        "destination_code": "SHA",
        "depart_date": "2099-08-01",
        "dep_time": "08:00",
        "arr_time": "10:00",
        "duration": "120分钟",
        "stops": 0,
    }
    await upsert_provider_flights(
        "ctrip_snapshot",
        [{**base, "prices": [{"platform": "携程", "price": 580, "url": "https://ctrip.test"}]}],
        ttl_minutes=75,
    )
    await upsert_flights(
        [{**base, "lowest_price": 600, "prices": [{"platform": "legacy", "price": 600, "url": "https://legacy.test"}]}]
    )

    rows, _, _ = await read_provider_deals(
        provider="ctrip_snapshot",
        origin_code="BJS",
        destination_code="SHA",
        depart_date="2099-08-01",
    )

    assert len(rows) == 1
    assert rows[0]["prices"][0]["platform"] == "携程"


@pytest.mark.asyncio
async def test_ctrip_only_snapshot_is_absent_from_legacy_reads(seeded_pg):
    await upsert_provider_flights(
        "ctrip_snapshot",
        [
            {
                "flight_no": "MU5106",
                "airline": "东方航空",
                "origin_code": "BJS",
                "destination_code": "SHA",
                "depart_date": "2099-08-01",
                "dep_time": "08:00",
                "arr_time": "10:00",
                "duration": "120分钟",
                "stops": 0,
                "prices": [{"platform": "携程", "price": 580, "url": "https://ctrip.test"}],
            }
        ],
        ttl_minutes=75,
    )

    assert await read_deals(
        origin_code="BJS", destination_code="SHA", depart_date="2099-08-01"
    ) == []
    assert await read_deals_latest(origin_code="BJS", destination_code="SHA") == []


@pytest.mark.asyncio
async def test_mixed_provider_rows_keep_legacy_price_and_freshness(seeded_pg):
    base = {
        "flight_no": "MU5106",
        "airline": "东方航空",
        "origin_code": "BJS",
        "destination_code": "SHA",
        "depart_date": "2099-08-01",
        "dep_time": "08:00",
        "arr_time": "10:00",
        "duration": "120分钟",
        "stops": 0,
    }
    await upsert_flights(
        [{**base, "lowest_price": 600, "prices": [{"platform": "legacy", "price": 600, "url": "https://legacy.test"}]}]
    )
    await upsert_provider_flights(
        "ctrip_snapshot",
        [{**base, "prices": [{"platform": "携程", "price": 580, "url": "https://ctrip.test"}]}],
        ttl_minutes=-1,
    )

    rows = await read_deals(
        origin_code="BJS", destination_code="SHA", depart_date="2099-08-01"
    )

    assert len(rows) == 1
    assert rows[0]["lowest_price"] == 600
    assert rows[0]["prices"] == [
        {
            "platform": "legacy",
            "price": 600,
            "url": "https://legacy.test",
            "lowest": True,
        }
    ]
    assert rows[0]["data_freshness"] == "fresh"


@pytest.mark.asyncio
async def test_read_deals_latest_ignores_newer_provider_only_snapshot(seeded_pg):
    base = {
        "airline": "东方航空",
        "origin_code": "BJS",
        "destination_code": "SHA",
        "dep_time": "08:00",
        "arr_time": "10:00",
        "duration": "120分钟",
        "stops": 0,
    }
    await upsert_flights(
        [
            {
                **base,
                "flight_no": "MU5106",
                "depart_date": "2099-08-01",
                "lowest_price": 600,
                "prices": [{"platform": "legacy", "price": 600, "url": "https://legacy.test"}],
            }
        ]
    )
    await upsert_provider_flights(
        "ctrip_snapshot",
        [
            {
                **base,
                "flight_no": "MU5108",
                "depart_date": "2099-08-02",
                "prices": [{"platform": "携程", "price": 580, "url": "https://ctrip.test"}],
            }
        ],
        ttl_minutes=75,
    )

    rows = await read_deals_latest(origin_code="BJS", destination_code="SHA")

    assert len(rows) == 1
    assert rows[0]["depart_date"] == "2099-08-01"
    assert rows[0]["prices"][0]["platform"] == "legacy"
