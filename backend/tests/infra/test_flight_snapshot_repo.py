import asyncio
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

import backend.infrastructure.db.flight_snapshot_repo as snapshot_repo
from backend.infrastructure.db.flight_snapshot_repo import (
    FlightSnapshot,
    PlatformPriceSnapshot,
    _deal_sort_key,
    read_deals,
    read_deals_latest,
    read_provider_deals,
    upsert_flights,
    upsert_provider_flights,
)


def test_deal_sort_key_groups_currency_before_numeric_amount():
    cny = {"currency": "CNY", "lowest_price": 550, "flight_no": "CNY550"}
    usd = {"currency": "USD", "lowest_price": 80, "flight_no": "USD80"}

    assert sorted([usd, cny], key=_deal_sort_key) == [cny, usd]


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
    assert rows[0]["currency"] == "CNY"
    assert len(rows[0]["prices"]) == 1
    assert rows[0]["prices"][0] == {
        "id": rows[0]["prices"][0]["id"],
        "platform": "legacy",
        "price": 600,
        "currency": "CNY",
        "url": "https://legacy.test",
        "lowest": True,
        "price_status": "priced",
        "data_provider": "legacy",
        "data_freshness": "fresh",
    }
    assert rows[0]["winning_price_id"] == rows[0]["prices"][0]["id"]
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


@pytest.mark.asyncio
async def test_read_deals_propagates_expired_and_unknown_price_freshness(
    seeded_pg,
    monkeypatch,
):
    now = datetime(2099, 7, 1, 0, 0, tzinfo=timezone.utc)

    class FrozenDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz is not None else now.replace(tzinfo=None)

    monkeypatch.setattr(snapshot_repo, "datetime", FrozenDateTime)
    base = {
        "airline": "东方航空",
        "origin_code": "BJS",
        "destination_code": "SHA",
        "depart_date": "2099-08-01",
        "arr_time": "10:00",
        "duration": "120分钟",
        "stops": 0,
    }
    await upsert_flights(
        [
            {
                **base,
                "flight_no": "EXPIRED",
                "dep_time": "08:00",
                "lowest_price": 500,
                "prices": [
                    {
                        "platform": "Expired Seller",
                        "price": 500,
                        "currency": "CNY",
                        "url": "https://expired.example.test/book",
                    }
                ],
            },
            {
                **base,
                "flight_no": "UNKNOWN",
                "dep_time": "09:00",
                "lowest_price": 520,
                "prices": [
                    {
                        "platform": "Unknown Seller",
                        "price": 520,
                        "currency": "CNY",
                        "url": "https://unknown.example.test/book",
                    }
                ],
            },
        ]
    )
    async with seeded_pg.begin() as connection:
        snapshot_ids = dict(
            (
                await connection.execute(
                    select(FlightSnapshot.flight_no, FlightSnapshot.id).where(
                        FlightSnapshot.flight_no.in_(["EXPIRED", "UNKNOWN"])
                    )
                )
            ).all()
        )
        await connection.execute(
            update(PlatformPriceSnapshot)
            .where(
                PlatformPriceSnapshot.flight_snapshot_id
                == snapshot_ids["EXPIRED"]
            )
            .values(expires_at=now - timedelta(seconds=1))
        )
        await connection.execute(
            update(PlatformPriceSnapshot)
            .where(
                PlatformPriceSnapshot.flight_snapshot_id
                == snapshot_ids["UNKNOWN"]
            )
            .values(expires_at=None)
        )

    deals = await read_deals(
        origin_code="BJS",
        destination_code="SHA",
        depart_date="2099-08-01",
    )
    by_flight = {deal["flight_no"]: deal for deal in deals}

    assert by_flight["EXPIRED"]["data_freshness"] == "stale"
    assert by_flight["EXPIRED"]["winning_price_id"] is None
    assert by_flight["EXPIRED"]["prices"][0]["data_freshness"] == "stale"
    assert by_flight["EXPIRED"]["prices"][0]["expires_at"] == (
        now - timedelta(seconds=1)
    ).isoformat()
    assert by_flight["EXPIRED"]["prices"][0]["lowest"] is False
    assert by_flight["UNKNOWN"]["data_freshness"] == "unknown"
    assert by_flight["UNKNOWN"]["winning_price_id"] is None
    assert by_flight["UNKNOWN"]["prices"][0]["data_freshness"] == "unknown"
    assert by_flight["UNKNOWN"]["prices"][0]["expires_at"] is None
    assert by_flight["UNKNOWN"]["prices"][0]["lowest"] is False


@pytest.mark.asyncio
async def test_provider_upsert_preserves_legacy_parent_history_and_crawl_state(
    seeded_pg,
):
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
        [
            {
                **base,
                "lowest_price": 600,
                "history_avg_90d": 720,
                "history_low_90d": 520,
                "prices": [
                    {
                        "platform": "legacy",
                        "price": 600,
                        "url": "https://legacy.test",
                    }
                ],
            }
        ]
    )
    legacy_crawled_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    legacy_expires_at = datetime(2099, 8, 1, tzinfo=timezone.utc)
    async with seeded_pg.begin() as connection:
        snapshot_id = (
            await connection.execute(
                select(FlightSnapshot.id).where(
                    FlightSnapshot.flight_no == "MU5106"
                )
            )
        ).scalar_one()
        await connection.execute(
            update(FlightSnapshot)
            .where(FlightSnapshot.id == snapshot_id)
            .values(
                crawled_at=legacy_crawled_at,
                expires_at=legacy_expires_at,
            )
        )

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

    deals = await read_deals(
        origin_code="BJS",
        destination_code="SHA",
        depart_date="2099-08-01",
    )
    async with seeded_pg.connect() as connection:
        parent = (
            await connection.execute(
                select(
                    FlightSnapshot.history_avg_90d,
                    FlightSnapshot.history_low_90d,
                    FlightSnapshot.crawled_at,
                    FlightSnapshot.expires_at,
                    FlightSnapshot.lowest_price,
                ).where(FlightSnapshot.id == snapshot_id)
            )
        ).one()

    assert deals[0]["history_avg_90d"] == 720
    assert deals[0]["history_low_90d"] == 520
    assert deals[0]["lowest_price"] == 600
    assert deals[0]["data_freshness"] == "fresh"
    assert parent.history_avg_90d == 720
    assert parent.history_low_90d == 520
    assert parent.crawled_at == legacy_crawled_at
    assert parent.expires_at == legacy_expires_at
    assert parent.lowest_price == 600


@pytest.mark.asyncio
async def test_provider_refresh_atomically_replaces_partial_route_inventory(
    seeded_pg,
):
    scope = {
        "origin_code": "BJS",
        "destination_code": "SHA",
        "depart_date": "2099-08-01",
    }
    base = {
        **scope,
        "airline": "东方航空",
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
                "flight_no": "MU5106",
                "prices": [{"platform": "携程", "price": 580}],
            },
            {
                **base,
                "flight_no": "MU5108",
                "dep_time": "09:00",
                "prices": [{"platform": "携程", "price": 620}],
            },
        ],
        ttl_minutes=75,
        **scope,
    )

    await upsert_provider_flights(
        "ctrip_snapshot",
        [
            {
                **base,
                "flight_no": "MU5108",
                "dep_time": "09:00",
                "prices": [{"platform": "携程", "price": 600}],
            }
        ],
        ttl_minutes=75,
        **scope,
    )
    rows, _, _ = await read_provider_deals(provider="ctrip_snapshot", **scope)

    assert [row["flight_no"] for row in rows] == ["MU5108"]
    assert rows[0]["lowest_price"] == 600


@pytest.mark.asyncio
async def test_provider_refresh_with_empty_success_clears_route_inventory(
    seeded_pg,
):
    scope = {
        "origin_code": "BJS",
        "destination_code": "SHA",
        "depart_date": "2099-08-01",
    }
    await upsert_provider_flights(
        "ctrip_snapshot",
        [
            {
                **scope,
                "flight_no": "MU5106",
                "airline": "东方航空",
                "dep_time": "08:00",
                "arr_time": "10:00",
                "duration": "120分钟",
                "stops": 0,
                "prices": [{"platform": "携程", "price": 580}],
            }
        ],
        ttl_minutes=75,
        **scope,
    )

    await upsert_provider_flights(
        "ctrip_snapshot",
        [],
        ttl_minutes=75,
        **scope,
    )
    rows, age, stale = await read_provider_deals(
        provider="ctrip_snapshot", **scope
    )

    assert rows == []
    assert age is not None
    assert stale is False


@pytest.mark.asyncio
async def test_empty_provider_observation_is_scoped_and_expires_by_ttl(
    seeded_pg,
    monkeypatch,
):
    observed_at = datetime(2099, 7, 1, 0, 0, tzinfo=timezone.utc)

    class FrozenDateTime(datetime):
        current = observed_at

        @classmethod
        def now(cls, tz=None):
            current = cls.current
            return current if tz is not None else current.replace(tzinfo=None)

    monkeypatch.setattr(snapshot_repo, "datetime", FrozenDateTime)
    target = {
        "origin_code": "BJS",
        "destination_code": "SHA",
        "depart_date": "2099-08-01",
    }
    other_route = {
        "origin_code": "BJS",
        "destination_code": "CAN",
        "depart_date": "2099-08-01",
    }
    other_date = {
        "origin_code": "BJS",
        "destination_code": "SHA",
        "depart_date": "2099-08-02",
    }

    await upsert_provider_flights(
        "legacy", [], ttl_minutes=120, **target
    )
    await upsert_provider_flights(
        "ctrip_snapshot", [], ttl_minutes=120, **other_route
    )
    await upsert_provider_flights(
        "ctrip_snapshot", [], ttl_minutes=120, **other_date
    )
    await upsert_provider_flights(
        "ctrip_snapshot", [], ttl_minutes=60, **target
    )

    rows, age, stale = await read_provider_deals(
        provider="ctrip_snapshot", **target
    )
    assert rows == []
    assert age == 0
    assert stale is False

    for provider, scope in (
        ("legacy", target),
        ("ctrip_snapshot", other_route),
        ("ctrip_snapshot", other_date),
    ):
        other_rows, other_age, other_stale = await read_provider_deals(
            provider=provider, **scope
        )
        assert other_rows == []
        assert other_age == 0
        assert other_stale is False

    FrozenDateTime.current = observed_at + timedelta(minutes=61)

    rows, age, stale = await read_provider_deals(
        provider="ctrip_snapshot", **target
    )
    assert rows == []
    assert age == 61 * 60
    assert stale is True

    for provider, scope in (
        ("legacy", target),
        ("ctrip_snapshot", other_route),
        ("ctrip_snapshot", other_date),
    ):
        _, _, other_stale = await read_provider_deals(
            provider=provider, **scope
        )
        assert other_stale is False


@pytest.mark.asyncio
async def test_read_deals_latest_excludes_historical_departures(seeded_pg):
    await upsert_flights(
        [
            {
                "flight_no": "PAST1",
                "airline": "东方航空",
                "origin_code": "BJS",
                "destination_code": "SHA",
                "depart_date": "2020-01-01",
                "dep_time": "08:00",
                "arr_time": "10:00",
                "duration": "2h",
                "stops": 0,
                "lowest_price": 280,
                "prices": [{"platform": "携程", "price": 280}],
            }
        ]
    )

    rows = await read_deals_latest(
        origin_code="BJS",
        destination_code="SHA",
        today=date(2026, 7, 18),
    )

    assert rows == []
