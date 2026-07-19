from __future__ import annotations

import json
from datetime import datetime, timezone

import httpx
import pytest

from backend.application.contracts.collector import CollectorErrorCode
from backend.application.contracts.flight_provider import FlightOffer, PriceStatus
from backend.collector.client import CollectorApiClient


@pytest.mark.asyncio
async def test_client_uses_bearer_token_and_claims_one_job():
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(
            200,
            json={
                "job": {
                    "job_id": "job-1",
                    "origin_code": "BJS",
                    "destination_code": "SHA",
                    "depart_date": "2099-08-08",
                    "source": "recent_search",
                    "priority": 50,
                    "attempts": 1,
                    "lease_expires_at": "2099-08-01T00:00:00Z",
                }
            },
        )

    client = CollectorApiClient(
        base_url="https://backend.example.test",
        token="collector-secret",
        node_id="mac-1",
        transport=httpx.MockTransport(handler),
    )
    try:
        job = await client.claim()
    finally:
        await client.close()

    assert job is not None
    assert job.job_id == "job-1"
    assert requests[0].url.path == "/internal/collector/claim"
    assert requests[0].headers["Authorization"] == "Bearer collector-secret"
    assert json.loads(requests[0].content) == {"node_id": "mac-1"}


@pytest.mark.asyncio
async def test_client_sends_only_normalized_offer_fields():
    payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        return httpx.Response(204)

    offer = FlightOffer(
        data_provider="ctrip",
        seller_name="携程",
        flight_no="MU5106",
        airline="东方航空",
        origin_city="北京",
        origin_code="BJS",
        origin_airport_code="PEK",
        destination_city="上海",
        destination_code="SHA",
        destination_airport_code="SHA",
        depart_date="2099-08-08",
        depart_time="08:00",
        arrive_time="10:00",
        duration_minutes=120,
        stops=0,
        cabin="Y",
        currency="CNY",
        base_price=430,
        tax=150,
        tax_source="regulatory_estimate",
        baggage_fee=0,
        baggage_allowance="20KG",
        has_baggage=True,
        total_price=580,
        price_status=PriceStatus.priced,
        booking_url=(
            "https://flights.ctrip.com/online/list/oneway-bjs-sha"
            "?depdate=2099-08-08"
        ),
        raw_reference="must-not-leave-the-mac",
    )
    client = CollectorApiClient(
        base_url="https://backend.example.test",
        token="collector-secret",
        node_id="mac-1",
        transport=httpx.MockTransport(handler),
    )
    try:
        await client.complete("job-1", [offer])
    finally:
        await client.close()

    wire_offer = payloads[0]["offers"][0]
    assert wire_offer["data_provider"] == "ctrip_snapshot"
    assert wire_offer["display_price"] == 580
    assert wire_offer["origin_airport_code"] == "PEK"
    assert wire_offer["destination_airport_code"] == "SHA"
    assert "raw_reference" not in wire_offer
    assert wire_offer["base_price"] == 430
    assert wire_offer["tax"] == 150
    assert wire_offer["tax_source"] == "regulatory_estimate"
    assert wire_offer["baggage_fee"] == 0
    assert wire_offer["baggage_allowance"] == "20KG"
    assert wire_offer["has_baggage"] is True


@pytest.mark.asyncio
async def test_client_serializes_failure_as_rfc3339():
    payloads: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        payloads.append(json.loads(request.content))
        return httpx.Response(204)

    client = CollectorApiClient(
        base_url="https://backend.example.test",
        token="collector-secret",
        node_id="mac-1",
        transport=httpx.MockTransport(handler),
    )
    try:
        await client.fail(
            "job-1",
            CollectorErrorCode.login_required,
            datetime(2099, 8, 1, 12, 0, tzinfo=timezone.utc),
        )
    finally:
        await client.close()

    assert payloads == [
        {
            "node_id": "mac-1",
            "error_code": "login_required",
            "retry_at": "2099-08-01T12:00:00Z",
        }
    ]


@pytest.mark.parametrize(
    ("base_url", "token"),
    [
        ("http://backend.example.test", "collector-secret"),
        ("https://backend.example.test/api", "collector-secret"),
        ("https://backend.example.test", ""),
        ("https://backend.example.test", "secret value"),
    ],
)
def test_client_fails_closed_for_unsafe_configuration(base_url, token):
    with pytest.raises(ValueError):
        CollectorApiClient(
            base_url=base_url,
            token=token,
            node_id="mac-1",
        )
