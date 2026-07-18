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
    fetched_at: str | None = None,
    booking_url: str | None = None,
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
        booking_url=booking_url
        or (
            "https://book.example.test/flight?utm_source=test"
            if price is None
            else "https://book.example.test/flight"
        ),
        fetched_at=fetched_at,
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
        False,
        False,
        False,
        True,
        False,
    ]
    assert deal["price"] == 530
    assert deal["total_price"] == 530
    assert deal["platform"] == "Fresh Air"
    winner = next(row for row in deal["prices"] if row["name"] == "Fresh Air")
    snapshot = next(row for row in deal["prices"] if row["name"] == "携程")
    assert deal["winning_price_id"] == winner["id"]
    assert deal["booking_url"] == winner["url"]
    assert snapshot["lowest"] is False
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

    status_row = deal["prices"][0]
    assert status_row == {
        "id": status_row["id"],
        "name": "携程",
        "price": None,
        "currency": "CNY",
        "lowest": False,
        "price_status": None,
        "provider_status": "timeout",
        "data_freshness": "unknown",
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


def test_price_rows_keep_currency_and_separate_provider_from_price_status():
    results = {
        "flyai": ProviderResult(
            provider="flyai",
            status=ProviderStatus.success,
            offers=[_offer(provider="flyai", seller="飞猪", price=550)],
        )
    }

    deal = offers_to_deals(_query(), results)[0]

    assert deal["recommend_score"] is None
    assert deal["currency"] == "CNY"
    assert deal["prices"][0]["currency"] == "CNY"
    assert deal["prices"][0]["price_status"] == "priced"
    assert deal["prices"][0]["provider_status"] == "success"
    assert deal["prices"][0]["data_freshness"] == "fresh"
    assert deal["data_freshness"] == "fresh"
    assert deal["winning_price_id"] == deal["prices"][0]["id"]
    assert deal["prices"][0]["id"]
    assert "status" not in deal["prices"][0]


def test_unlike_currencies_are_not_compared_as_raw_amounts():
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

    deal = offers_to_deals(_query(), results)[0]
    rows = {row["currency"]: row for row in deal["prices"]}

    assert deal["currency"] == "CNY"
    assert deal["price"] == 550
    assert rows["CNY"]["lowest"] is True
    assert rows["USD"]["lowest"] is False


def test_duplicate_provider_seller_currency_rows_collapse_deterministically():
    results = {
        "flyai": ProviderResult(
            provider="flyai",
            status=ProviderStatus.success,
            offers=[
                _offer(provider="flyai", seller="飞猪", price=600),
                _offer(provider="flyai", seller="飞猪", price=550),
            ],
        )
    }

    deal = offers_to_deals(_query(), results)[0]

    assert len(deal["prices"]) == 1
    assert deal["prices"][0]["price"] == 550


def test_duplicate_equal_prices_keep_the_freshest_offer():
    results = {
        "flyai": ProviderResult(
            provider="flyai",
            status=ProviderStatus.success,
            offers=[
                _offer(
                    provider="flyai",
                    seller="飞猪",
                    price=550,
                    fetched_at="2099-08-01T00:00:00+00:00",
                    booking_url="https://book.example.test/flight?offer=old",
                ),
                _offer(
                    provider="flyai",
                    seller="飞猪",
                    price=550,
                    fetched_at="2099-08-01T00:05:00+00:00",
                    booking_url="https://book.example.test/flight?offer=new",
                ),
            ],
        )
    }

    deal = offers_to_deals(_query(), results)[0]

    assert len(deal["prices"]) == 1
    assert deal["prices"][0]["url"].endswith("?offer=new")


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
