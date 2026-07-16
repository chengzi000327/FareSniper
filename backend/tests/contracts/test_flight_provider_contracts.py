from backend.application.contracts.flight_provider import (
    FlightOffer,
    PriceStatus,
    ProviderResult,
    ProviderStatus,
)


def test_offer_keeps_unknown_fees_and_live_link():
    offer = FlightOffer(
        data_provider="flyai",
        seller_name="飞猪",
        flight_no="CA1835",
        origin_city="北京",
        origin_code="BJS",
        destination_city="上海",
        destination_code="SHA",
        depart_date="2099-08-01",
        total_price=None,
        tax=None,
        baggage_fee=None,
        has_baggage=None,
        price_status=PriceStatus.view_live_price,
        booking_url="https://example.test/flight",
    )
    assert offer.total_price is None
    assert offer.price_status is PriceStatus.view_live_price


def test_disabled_and_empty_are_distinct():
    assert ProviderResult(
        provider="flyai", status=ProviderStatus.disabled
    ).status != ProviderResult(provider="flyai", status=ProviderStatus.empty).status
