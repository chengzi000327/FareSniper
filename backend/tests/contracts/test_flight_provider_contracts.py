from backend.application.contracts.flight_provider import (
    FlightOffer,
    PriceStatus,
    ProviderResult,
    ProviderStatus,
)
from pydantic import ValidationError
import pytest


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


def test_unpriced_offer_requires_view_live_price_status():
    with pytest.raises(ValidationError):
        FlightOffer(
            data_provider="flyai",
            seller_name="飞猪",
            flight_no="CA1835",
            origin_city="北京",
            origin_code="BJS",
            destination_city="上海",
            destination_code="SHA",
            depart_date="2099-08-01",
            total_price=None,
            booking_url="https://example.test/flight",
        )


@pytest.mark.parametrize("booking_url", [None, "http://example.test/flight"])
def test_unpriced_live_offer_requires_https_link(booking_url):
    with pytest.raises(ValidationError):
        FlightOffer(
            data_provider="flyai",
            seller_name="飞猪",
            flight_no="CA1835",
            origin_city="北京",
            origin_code="BJS",
            destination_city="上海",
            destination_code="SHA",
            depart_date="2099-08-01",
            total_price=None,
            price_status=PriceStatus.view_live_price,
            booking_url=booking_url,
        )


def test_view_live_price_requires_unknown_total_price():
    with pytest.raises(ValidationError):
        FlightOffer(
            data_provider="flyai",
            seller_name="飞猪",
            flight_no="CA1835",
            origin_city="北京",
            origin_code="BJS",
            destination_city="上海",
            destination_code="SHA",
            depart_date="2099-08-01",
            total_price=999,
            price_status=PriceStatus.view_live_price,
            booking_url="https://example.test/flight",
        )


def test_disabled_and_empty_are_distinct():
    assert ProviderResult(
        provider="flyai", status=ProviderStatus.disabled
    ).status != ProviderResult(provider="flyai", status=ProviderStatus.empty).status
