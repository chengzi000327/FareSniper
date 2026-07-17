from __future__ import annotations

import pytest

from backend.application.contracts.flight_provider import PriceStatus, ProviderStatus
from backend.application.services.flight_query import build_flight_query
from backend.infrastructure.flight_data.providers.ctrip_snapshot import (
    CtripSnapshotProvider,
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

    monkeypatch.setattr(
        "backend.infrastructure.flight_data.providers.ctrip_snapshot.read_provider_deals",
        read_rows,
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
