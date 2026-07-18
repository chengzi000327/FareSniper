from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, update

import backend.infrastructure.db.flight_demand_repo as demand_repo
import backend.infrastructure.db.flight_snapshot_repo as snapshot_repo
import backend.infrastructure.flight_data.providers.ctrip_snapshot as ctrip_provider
from backend.application.contracts.flight_provider import PriceStatus, ProviderStatus
from backend.application.services.flight_query import build_flight_query
from backend.infrastructure.db.base import get_session
from backend.infrastructure.db.flight_demand_repo import (
    FlightSearchDemandRow,
    enqueue_demand,
)
from backend.infrastructure.db.flight_snapshot_repo import upsert_provider_flights
from backend.infrastructure.flight_data.providers.ctrip_snapshot import (
    CtripSnapshotProvider,
    ctrip_rows_to_offers,
)


@pytest.mark.asyncio
async def test_empty_snapshot_queues_demand(monkeypatch):
    queued = []

    async def read_empty(**kwargs):
        return [], None, False

    async def capture_demand(**kwargs):
        queued.append(kwargs)

    monkeypatch.setattr(
        "backend.infrastructure.flight_data.providers.ctrip_snapshot.read_provider_deals",
        read_empty,
    )
    monkeypatch.setattr(
        "backend.infrastructure.flight_data.providers.ctrip_snapshot.enqueue_demand",
        capture_demand,
    )
    query = build_flight_query("北京", "上海", "2099-08-01")

    result = await CtripSnapshotProvider().search(query)

    assert result.status is ProviderStatus.queued
    assert result.message == "等待下次刷新"
    assert queued == [
        {
            "origin_code": "BJS",
            "destination_code": "SHA",
            "depart_date": "2099-08-01",
            "priority": 50,
            "source": "recent_search",
        }
    ]


@pytest.mark.asyncio
async def test_empty_ctrip_refresh_is_not_observed_as_success(
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

    queued = []

    async def capture_demand(**kwargs):
        queued.append(kwargs)

    monkeypatch.setattr(snapshot_repo, "datetime", FrozenDateTime)
    monkeypatch.setattr(
        "backend.infrastructure.flight_data.providers.ctrip_snapshot.enqueue_demand",
        capture_demand,
    )
    await upsert_provider_flights(
        "ctrip_snapshot",
        [],
        ttl_minutes=60,
        origin_code="BJS",
        destination_code="SHA",
        depart_date="2099-08-01",
    )
    query = build_flight_query("北京", "上海", "2099-08-01")

    result = await CtripSnapshotProvider().search(query)

    assert result.status is ProviderStatus.queued
    assert result.offers == []
    assert result.cache_age_seconds is None
    assert len(queued) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("stale", "expected_status", "expected_price_status"),
    [
        (False, ProviderStatus.success, PriceStatus.priced),
        (True, ProviderStatus.stale, PriceStatus.stale),
    ],
)
async def test_snapshot_rows_map_to_non_realtime_ctrip_offers(
    monkeypatch, stale, expected_status, expected_price_status
):
    queued = []

    async def read_rows(**kwargs):
        return [
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
                "lowest_price": 580,
                "prices": [
                    {
                        "platform": "携程",
                        "price": 580,
                        "url": "https://ctrip.test/book",
                        "currency": "CNY",
                        "price_status": "priced",
                        "crawled_at": "2099-07-31T23:50:00+00:00",
                        "expires_at": (
                            "2000-01-01T00:00:00+00:00"
                            if stale
                            else "2099-08-01T01:05:00+00:00"
                        ),
                    }
                ],
            }
        ], 600, stale

    async def capture_demand(**kwargs):
        queued.append(kwargs)

    monkeypatch.setattr(
        "backend.infrastructure.flight_data.providers.ctrip_snapshot.read_provider_deals",
        read_rows,
    )
    monkeypatch.setattr(
        "backend.infrastructure.flight_data.providers.ctrip_snapshot.enqueue_demand",
        capture_demand,
    )
    query = build_flight_query("北京", "上海", "2099-08-01")

    result = await CtripSnapshotProvider().search(query)

    assert result.status is expected_status
    assert result.cache_age_seconds == 600
    assert len(result.offers) == 1
    offer = result.offers[0]
    assert offer.seller_name == "携程"
    assert offer.data_provider == "ctrip_snapshot"
    assert offer.total_price == 580
    assert offer.duration_minutes == 120
    assert offer.tax is None
    assert offer.baggage_fee is None
    assert offer.has_baggage is None
    assert offer.is_realtime is False
    assert offer.price_status is expected_price_status
    assert len(queued) == int(stale)


@pytest.mark.asyncio
async def test_stale_nonempty_snapshot_returns_reference_offers_and_renews_demand(
    monkeypatch,
):
    queued = []

    async def read_stale_rows(**kwargs):
        return [
            {
                "flight_no": "MU5106",
                "airline": "东方航空",
                "dep_time": "08:00",
                "arr_time": "10:00",
                "duration": "120分钟",
                "stops": 0,
                "prices": [
                    {
                        "id": "snapshot-row",
                        "platform": "携程",
                        "price": 580,
                        "currency": "CNY",
                        "url": "https://ctrip.test/reference",
                        "expires_at": "2000-01-01T00:00:00+00:00",
                    }
                ],
            }
        ], 3601, True

    async def capture_demand(**kwargs):
        queued.append(kwargs)

    monkeypatch.setattr(
        "backend.infrastructure.flight_data.providers.ctrip_snapshot.read_provider_deals",
        read_stale_rows,
    )
    monkeypatch.setattr(
        "backend.infrastructure.flight_data.providers.ctrip_snapshot.enqueue_demand",
        capture_demand,
    )

    result = await CtripSnapshotProvider().search(
        build_flight_query("北京", "上海", "2099-08-01")
    )

    assert result.status is ProviderStatus.stale
    assert len(result.offers) == 1
    assert result.offers[0].price_status is PriceStatus.stale
    assert queued == [
        {
            "origin_code": "BJS",
            "destination_code": "SHA",
            "depart_date": "2099-08-01",
            "priority": 50,
            "source": "recent_search",
        }
    ]


@pytest.mark.asyncio
async def test_provider_rechecks_expiry_after_repository_await_and_renews_demand(
    monkeypatch,
):
    before_expiry = datetime(2099, 8, 1, 0, 59, 59, tzinfo=timezone.utc)
    expiry = before_expiry + timedelta(seconds=1)

    class FrozenDateTime(datetime):
        current = before_expiry

        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return cls.current.replace(tzinfo=None)
            return cls.current.astimezone(tz)

    queued = []

    async def read_crossing_rows(**kwargs):
        FrozenDateTime.current = expiry
        return [
            {
                "flight_no": "MU5106",
                "airline": "东方航空",
                "dep_time": "08:00",
                "arr_time": "10:00",
                "duration": "120分钟",
                "stops": 0,
                "prices": [
                    {
                        "id": "snapshot-row",
                        "platform": "携程",
                        "price": 580,
                        "currency": "CNY",
                        "url": "https://ctrip.test/reference",
                        "crawled_at": before_expiry.isoformat(),
                        "expires_at": expiry.isoformat(),
                    }
                ],
            }
        ], 60 * 60, False

    async def capture_demand(**kwargs):
        queued.append(kwargs)

    monkeypatch.setattr(ctrip_provider, "datetime", FrozenDateTime)
    monkeypatch.setattr(ctrip_provider, "read_provider_deals", read_crossing_rows)
    monkeypatch.setattr(ctrip_provider, "enqueue_demand", capture_demand)

    result = await CtripSnapshotProvider().search(
        build_flight_query("北京", "上海", "2099-08-01")
    )

    assert result.status is ProviderStatus.stale
    assert result.offers[0].price_status is PriceStatus.stale
    assert len(queued) == 1


@pytest.mark.asyncio
async def test_stale_nonempty_snapshot_reactivates_expired_demand_without_duplicates(
    seeded_pg,
    monkeypatch,
):
    observed_at = datetime(2099, 7, 1, 0, 0, tzinfo=timezone.utc)

    class FrozenDateTime(datetime):
        current = observed_at

        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return cls.current.replace(tzinfo=None)
            return cls.current.astimezone(tz)

    monkeypatch.setattr(snapshot_repo, "datetime", FrozenDateTime)
    monkeypatch.setattr(demand_repo, "datetime", FrozenDateTime)
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
                "prices": [
                    {
                        "platform": "携程",
                        "price": 580,
                        "currency": "CNY",
                        "url": "https://ctrip.test/reference",
                    }
                ],
            }
        ],
        ttl_minutes=60,
        **scope,
    )
    await enqueue_demand(
        **scope,
        priority=10,
        source="recent_search",
    )
    async with get_session() as session:
        await session.execute(
            update(FlightSearchDemandRow)
            .where(
                FlightSearchDemandRow.origin_code == "BJS",
                FlightSearchDemandRow.destination_code == "SHA",
                FlightSearchDemandRow.depart_date == "2099-08-01",
            )
            .values(
                active=False,
                expires_at=observed_at - timedelta(days=1),
                next_run_at=observed_at - timedelta(days=1),
            )
        )
        await session.commit()

    FrozenDateTime.current = observed_at + timedelta(minutes=61)
    query = build_flight_query("北京", "上海", "2099-08-01")

    first = await CtripSnapshotProvider().search(query)
    second = await CtripSnapshotProvider().search(query)

    async with get_session() as session:
        demands = (
            await session.execute(select(FlightSearchDemandRow))
        ).scalars().all()

    assert first.status is ProviderStatus.stale
    assert second.status is ProviderStatus.stale
    assert len(first.offers) == 1
    assert len(demands) == 2
    active_demands = [demand for demand in demands if demand.active]
    assert len(active_demands) == 1
    refreshed = active_demands[0]
    assert refreshed.demand_hour == FrozenDateTime.current.replace(
        minute=0, second=0, microsecond=0
    )
    assert refreshed.source == "recent_search"
    assert refreshed.priority == 50
    assert refreshed.last_requested_at == FrozenDateTime.current
    assert refreshed.expires_at == FrozenDateTime.current + timedelta(days=7)


@pytest.mark.asyncio
async def test_mixed_freshness_sets_price_status_per_offer(monkeypatch):
    async def read_rows(**kwargs):
        return [
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
                        "url": "https://ctrip.test/expired",
                        "currency": "CNY",
                        "crawled_at": "2000-01-01T00:00:00+00:00",
                        "expires_at": "2000-01-01T01:15:00+00:00",
                    }
                ],
            },
            {
                "flight_no": "MU5108",
                "airline": "东方航空",
                "origin_code": "BJS",
                "destination_code": "SHA",
                "depart_date": "2099-08-01",
                "dep_time": "09:00",
                "arr_time": "11:00",
                "duration": "120分钟",
                "stops": 0,
                "prices": [
                    {
                        "platform": "携程",
                        "price": 600,
                        "url": "https://ctrip.test/fresh",
                        "currency": "CNY",
                        "crawled_at": "2099-07-31T23:50:00+00:00",
                        "expires_at": "2099-08-01T01:05:00+00:00",
                    }
                ],
            },
        ], 600, False

    monkeypatch.setattr(
        "backend.infrastructure.flight_data.providers.ctrip_snapshot.read_provider_deals",
        read_rows,
    )
    query = build_flight_query("北京", "上海", "2099-08-01")

    result = await CtripSnapshotProvider().search(query)

    statuses = {offer.flight_no: offer.price_status for offer in result.offers}
    assert result.status is ProviderStatus.success
    assert statuses == {
        "MU5106": PriceStatus.stale,
        "MU5108": PriceStatus.priced,
    }


def test_snapshot_price_selection_prefers_query_currency_before_amount():
    query = build_flight_query("北京", "上海", "2099-08-01")
    rows = [
        {
            "flight_no": "MU5106",
            "airline": "东方航空",
            "dep_time": "08:00",
            "arr_time": "10:00",
            "prices": [
                {"platform": "Global", "price": 80, "currency": "USD"},
                {"platform": "携程", "price": 550, "currency": "CNY"},
            ],
        }
    ]

    offer = ctrip_rows_to_offers(rows, query, stale=False)[0]

    assert offer.currency == "CNY"
    assert offer.total_price == 550
