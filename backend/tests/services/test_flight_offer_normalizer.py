from __future__ import annotations

from backend.application.contracts.flight_provider import (
    FlightOffer,
    PriceStatus,
    ProviderResult,
    ProviderStatus,
)
from backend.application.services.flight_offer_normalizer import (
    offers_to_deals,
    rank_deals,
)
from backend.application.services.flight_query import build_flight_query


def _query():
    return build_flight_query("北京", "上海", "2099-08-01")


def _offer(
    *,
    provider: str,
    seller: str,
    price: int | None,
    flight_no: str = "CA1835",
    depart_time: str = "08:00",
    stops: int = 0,
    status: PriceStatus = PriceStatus.priced,
    realtime: bool = True,
    currency: str = "CNY",
) -> FlightOffer:
    return FlightOffer(
        data_provider=provider,
        seller_name=seller,
        flight_no=flight_no,
        airline="中国国航",
        origin_city="北京",
        origin_code="BJS",
        destination_city="上海",
        destination_code="SHA",
        depart_date="2099-08-01",
        depart_time=depart_time,
        arrive_time="10:10",
        duration_minutes=130,
        stops=stops,
        currency=currency,
        total_price=price,
        tax=None,
        baggage_fee=None,
        has_baggage=None,
        price_status=status,
        booking_url=(
            "https://book.example.test/flight?utm_source=test"
            if price is None
            else "https://book.example.test/flight"
        ),
        is_realtime=realtime,
    )


def test_deduplicates_identity_and_orders_price_rows_stably():
    results = {
        "flyai": ProviderResult(
            provider="flyai",
            status=ProviderStatus.success,
            offers=[_offer(provider="flyai", seller="飞猪", price=550)],
        ),
        "ctrip": ProviderResult(
            provider="ctrip",
            status=ProviderStatus.success,
            offers=[
                _offer(
                    provider="ctrip_snapshot",
                    seller="携程",
                    price=500,
                    realtime=False,
                )
            ],
        ),
        "serpapi": ProviderResult(
            provider="serpapi",
            status=ProviderStatus.success,
            offers=[
                _offer(
                    provider="serpapi_google_flights",
                    seller="Stale Air",
                    price=400,
                    status=PriceStatus.stale,
                ),
                _offer(
                    provider="serpapi_google_flights",
                    seller="Fresh Air",
                    price=530,
                ),
                _offer(
                    provider="serpapi_google_flights",
                    seller="Live Link",
                    price=None,
                    status=PriceStatus.view_live_price,
                ),
            ],
        ),
    }

    deals = offers_to_deals(_query(), results)

    assert len(deals) == 1
    deal = deals[0]
    assert [row["name"] for row in deal["prices"]] == [
        "携程",
        "飞猪",
        "Stale Air",
        "Fresh Air",
        "Live Link",
    ]
    assert [row["lowest"] for row in deal["prices"]] == [
        True,
        False,
        False,
        False,
        False,
    ]
    assert deal["price"] == 530
    assert deal["total_price"] == 530
    assert deal["platform"] == "Fresh Air"
    assert deal["tax"] is None
    assert deal["baggage_fee"] is None
    assert deal["has_baggage"] is None


def test_status_rows_cover_provider_without_offers():
    results = {
        "flyai": ProviderResult(
            provider="flyai",
            status=ProviderStatus.success,
            offers=[_offer(provider="flyai", seller="飞猪", price=550)],
        ),
        "ctrip": ProviderResult(
            provider="ctrip",
            status=ProviderStatus.timeout,
            error_code="timeout",
        ),
    }

    deal = offers_to_deals(_query(), results)[0]

    assert deal["prices"][0] == {
        "name": "携程",
        "price": None,
        "lowest": False,
        "status": "timeout",
        "url": None,
        "data_provider": "ctrip_snapshot",
    }


def test_provider_statuses_without_any_offer_do_not_create_fare_card():
    results = {
        status.value: ProviderResult(provider=status.value, status=status)
        for status in (
            ProviderStatus.loading,
            ProviderStatus.queued,
            ProviderStatus.timeout,
            ProviderStatus.error,
            ProviderStatus.disabled,
            ProviderStatus.empty,
        )
    }

    assert offers_to_deals(_query(), results) == []


def test_dedup_identity_does_not_include_currency():
    results = {
        "flyai": ProviderResult(
            provider="flyai",
            status=ProviderStatus.success,
            offers=[
                _offer(
                    provider="flyai",
                    seller="飞猪",
                    price=550,
                    currency="CNY",
                )
            ],
        ),
        "serpapi": ProviderResult(
            provider="serpapi",
            status=ProviderStatus.success,
            offers=[
                _offer(
                    provider="serpapi_google_flights",
                    seller="Global Air",
                    price=80,
                    currency="USD",
                )
            ],
        ),
    }

    deals = offers_to_deals(_query(), results)

    assert len(deals) == 1
    assert len(deals[0]["prices"]) == 2


def test_zero_is_a_numeric_price_and_can_win():
    results = {
        "flyai": ProviderResult(
            provider="flyai",
            status=ProviderStatus.success,
            offers=[
                _offer(provider="flyai", seller="Zero Fare", price=0),
                _offer(provider="flyai", seller="Paid Fare", price=5),
            ],
        )
    }

    deal = offers_to_deals(_query(), results)[0]

    assert deal["price"] == 0
    assert [row["lowest"] for row in deal["prices"]] == [True, False]


def test_rank_uses_realtime_price_then_stops_then_departure():
    results = {
        "ctrip": ProviderResult(
            provider="ctrip",
            status=ProviderStatus.success,
            offers=[
                _offer(
                    provider="ctrip_snapshot",
                    seller="携程",
                    price=100,
                    flight_no="SNAPSHOT",
                    depart_time="07:00",
                    realtime=False,
                )
            ],
        ),
        "flyai": ProviderResult(
            provider="flyai",
            status=ProviderStatus.success,
            offers=[
                _offer(
                    provider="flyai",
                    seller="飞猪",
                    price=600,
                    flight_no="ONE_STOP",
                    depart_time="06:00",
                    stops=1,
                ),
                _offer(
                    provider="flyai",
                    seller="飞猪",
                    price=600,
                    flight_no="LATE",
                    depart_time="10:00",
                ),
                _offer(
                    provider="flyai",
                    seller="飞猪",
                    price=600,
                    flight_no="EARLY",
                    depart_time="08:00",
                ),
            ],
        ),
    }

    ranked = rank_deals(offers_to_deals(_query(), results))

    assert [deal["flight_no"] for deal in ranked] == [
        "EARLY",
        "LATE",
        "ONE_STOP",
        "SNAPSHOT",
    ]
    assert ranked[-1]["price"] is None
