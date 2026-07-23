import pytest

from backend.application.services.flight_query import FlightQueryValidationError
from backend.workers import alert_checker
from backend.workers.alert_checker import _deal_price


def test_deal_price_prefers_normalized_total_price():
    assert _deal_price({"price": 500, "total_price": 650}) == 650


def test_deal_price_rejects_missing_or_boolean_values():
    assert _deal_price({"price": None}) is None
    assert _deal_price({"price": True}) is None


@pytest.mark.asyncio
async def test_refresh_route_queries_providers_and_writes_cache(monkeypatch):
    query = object()
    deals = [{"flight_no": "MU001", "total_price": 520}]
    writes = []

    monkeypatch.setattr(alert_checker, "build_flight_query", lambda *_: query)
    monkeypatch.setattr(alert_checker, "build_flight_providers", lambda: ["flyai"])

    class FakeAggregator:
        def __init__(self, providers, *, timeout_seconds):
            assert providers == ["flyai"]
            assert timeout_seconds > 0

        async def collect(self, received_query):
            assert received_query is query
            return {"deals": deals}

    async def write(**kwargs):
        writes.append(kwargs)

    monkeypatch.setattr(alert_checker, "FlightSearchAggregator", FakeAggregator)
    monkeypatch.setattr(alert_checker, "write_cached_deals", write)

    result = await alert_checker._refresh_route_deals(
        origin="BJS",
        destination="SYX",
        depart_date="2099-08-01",
    )

    assert result == deals
    assert writes == [
        {
            "origin": "BJS",
            "destination": "SYX",
            "depart_date": "2099-08-01",
            "deals": deals,
        }
    ]


@pytest.mark.asyncio
async def test_refresh_route_skips_invalid_query(monkeypatch):
    def invalid_query(*_args):
        raise FlightQueryValidationError("invalid")

    monkeypatch.setattr(alert_checker, "build_flight_query", invalid_query)

    assert (
        await alert_checker._refresh_route_deals(
            origin="BAD",
            destination="SYX",
            depart_date="2099-08-01",
        )
        == []
    )
