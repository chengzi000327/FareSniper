from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import httpx
import pytest

from backend.application.contracts.flight_provider import ProviderStatus
from backend.application.services.flight_query import build_flight_query
from backend.infrastructure.flight_data.providers.serpapi import SerpApiProvider


FIXTURES = Path(__file__).parents[1] / "fixtures/providers"
SEARCH = json.loads((FIXTURES / "serpapi_search.json").read_text())
BOOKING = json.loads((FIXTURES / "serpapi_booking_options.json").read_text())


@pytest.mark.asyncio
async def test_uses_actual_booking_seller():
    async def handler(request):
        payload = BOOKING if request.url.params.get("booking_token") else SEARCH
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    provider = SerpApiProvider(api_key="secret", client=client)
    result = await provider.search(
        build_flight_query("上海", "新加坡", "2099-08-01")
    )
    await client.aclose()

    assert result.status is ProviderStatus.success
    assert result.offers[0].seller_name == "Trip.com"
    assert result.offers[0].data_provider == "serpapi_google_flights"
    assert result.offers[0].total_price == 2860
    assert result.offers[0].booking_url == "https://booking.example.com/checkout"
    assert result.offers[0].tax is None
    assert result.offers[0].baggage_fee is None
    assert result.offers[0].has_baggage is None


@pytest.mark.asyncio
async def test_retains_response_currency_instead_of_assuming_query_currency():
    search = deepcopy(SEARCH)
    booking = deepcopy(BOOKING)
    search["search_parameters"] = {"currency": "USD"}
    booking["search_parameters"] = {"currency": "USD"}
    booking["booking_options"][0]["together"]["currency"] = "USD"
    booking["booking_options"][0]["together"]["booking_request"]["url"] = (
        "https://booking.example.com/checkout"
        "?offer=fixture-usd-token-not-secret"
    )

    async def handler(request):
        payload = booking if request.url.params.get("booking_token") else search
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await SerpApiProvider(api_key="secret", client=client).search(
        build_flight_query("上海", "新加坡", "2099-08-01")
    )
    await client.aclose()

    assert result.status is ProviderStatus.success
    assert result.offers[0].currency == "USD"
    assert result.offers[0].booking_url.endswith(
        "?offer=fixture-usd-token-not-secret"
    )


def test_mainland_route_is_not_supported():
    assert SerpApiProvider(api_key="x").supports(
        build_flight_query("北京", "上海", "2099-08-01")
    ) is False


def test_exact_international_airports_are_sent_as_single_ids():
    provider = SerpApiProvider(api_key="secret")
    query = build_flight_query("HND", "JFK", "2099-08-01")

    params = provider._search_params(query)

    assert params["departure_id"] == "HND"
    assert params["arrival_id"] == "JFK"


@pytest.mark.asyncio
async def test_search_uses_google_flights_request_parameters():
    requests = []

    async def handler(request):
        requests.append(request)
        payload = BOOKING if request.url.params.get("booking_token") else SEARCH
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await SerpApiProvider(api_key="secret", client=client).search(
        build_flight_query("上海", "新加坡", "2099-08-01")
    )
    await client.aclose()

    params = requests[0].url.params
    assert result.status is ProviderStatus.success
    assert params["engine"] == "google_flights"
    assert params["departure_id"] == "PVG,SHA"
    assert params["arrival_id"] == "SIN"
    assert params["outbound_date"] == "2099-08-01"
    assert params["type"] == "2"
    assert params["currency"] == "CNY"
    assert params["hl"] == "zh-cn"
    assert params["gl"] == "cn"
    assert params["sort_by"] == "2"
    assert params["adults"] == "1"
    assert params["api_key"] == "secret"


@pytest.mark.asyncio
async def test_post_only_booking_request_falls_back_to_google_flights_url():
    booking = deepcopy(BOOKING)
    booking["booking_options"][0]["together"]["booking_request"]["post_data"] = {
        "token": "redacted"
    }

    async def handler(request):
        payload = booking if request.url.params.get("booking_token") else SEARCH
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await SerpApiProvider(api_key="secret", client=client).search(
        build_flight_query("上海", "新加坡", "2099-08-01")
    )
    await client.aclose()

    assert result.offers[0].booking_url == SEARCH["search_metadata"]["google_flights_url"]


@pytest.mark.asyncio
async def test_empty_post_data_booking_request_falls_back_to_google_flights_url():
    booking = deepcopy(BOOKING)
    booking["booking_options"][0]["together"]["booking_request"]["post_data"] = {}

    async def handler(request):
        payload = booking if request.url.params.get("booking_token") else SEARCH
        return httpx.Response(200, json=payload)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await SerpApiProvider(api_key="secret", client=client).search(
        build_flight_query("上海", "新加坡", "2099-08-01")
    )
    await client.aclose()

    assert result.offers[0].booking_url == SEARCH["search_metadata"]["google_flights_url"]


@pytest.mark.asyncio
async def test_resolves_booking_options_for_only_three_cheapest_token_itineraries():
    search = deepcopy(SEARCH)
    extra_itineraries = []
    for price in (2900, 2800, 2700, 2600):
        itinerary = deepcopy(search["best_flights"][0])
        itinerary["price"] = price
        itinerary["booking_token"] = f"token-{price}"
        extra_itineraries.append(itinerary)
    search["other_flights"] = extra_itineraries
    booking_tokens = []

    async def handler(request):
        token = request.url.params.get("booking_token")
        if token:
            booking_tokens.append(token)
            return httpx.Response(200, json=BOOKING)
        return httpx.Response(200, json=search)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await SerpApiProvider(api_key="secret", client=client).search(
        build_flight_query("上海", "新加坡", "2099-08-01")
    )
    await client.aclose()

    assert result.status is ProviderStatus.success
    assert set(booking_tokens) == {"token-2600", "token-2700", "token-2800"}


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [401, 403])
async def test_authentication_errors_are_not_retried(status_code):
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(status_code, json={"error": "unauthorized"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await SerpApiProvider(api_key="secret", client=client).search(
        build_flight_query("上海", "新加坡", "2099-08-01")
    )
    await client.aclose()

    assert calls == 1
    assert result.status is ProviderStatus.error
    assert result.error_code == "authentication"


@pytest.mark.asyncio
async def test_temporary_5xx_retries_once_then_succeeds(monkeypatch):
    calls = 0
    search = deepcopy(SEARCH)
    search["best_flights"][0].pop("booking_token")

    async def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, json={"error": "temporary"})
        return httpx.Response(200, json=search)

    async def no_sleep(*args, **kwargs):
        return None

    monkeypatch.setattr("backend.infrastructure.flight_data.providers.serpapi.asyncio.sleep", no_sleep)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await SerpApiProvider(api_key="secret", client=client).search(
        build_flight_query("上海", "新加坡", "2099-08-01")
    )
    await client.aclose()

    assert calls == 2
    assert result.status is ProviderStatus.success


@pytest.mark.asyncio
async def test_429_retries_once_then_succeeds(monkeypatch):
    calls = 0
    search = deepcopy(SEARCH)
    search["best_flights"][0].pop("booking_token")

    async def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(429, json={"error": "rate limited"})
        return httpx.Response(200, json=search)

    async def no_sleep(*args, **kwargs):
        return None

    monkeypatch.setattr("backend.infrastructure.flight_data.providers.serpapi.asyncio.sleep", no_sleep)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await SerpApiProvider(api_key="secret", client=client).search(
        build_flight_query("上海", "新加坡", "2099-08-01")
    )
    await client.aclose()

    assert calls == 2
    assert result.status is ProviderStatus.success


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(lambda: httpx.TimeoutException("timed out"), id="timeout"),
        pytest.param(lambda: httpx.RemoteProtocolError("connection reset"), id="protocol"),
        pytest.param(lambda: httpx.ProxyError("proxy reset"), id="proxy"),
    ],
)
async def test_transient_transport_failure_retries_once_then_succeeds(failure, monkeypatch):
    calls = 0
    search = deepcopy(SEARCH)
    search["best_flights"][0].pop("booking_token")

    async def handler(request):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise failure()
        return httpx.Response(200, json=search)

    async def no_sleep(*args, **kwargs):
        return None

    monkeypatch.setattr("backend.infrastructure.flight_data.providers.serpapi.asyncio.sleep", no_sleep)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await SerpApiProvider(api_key="secret", client=client).search(
        build_flight_query("上海", "新加坡", "2099-08-01")
    )
    await client.aclose()

    assert calls == 2
    assert result.status is ProviderStatus.success


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "failure",
    [
        pytest.param(lambda: httpx.RemoteProtocolError("connection reset"), id="protocol"),
        pytest.param(lambda: httpx.ProxyError("proxy reset"), id="proxy"),
    ],
)
async def test_repeated_transport_failure_returns_network_error(failure, monkeypatch):
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        raise failure()

    async def no_sleep(*args, **kwargs):
        return None

    monkeypatch.setattr("backend.infrastructure.flight_data.providers.serpapi.asyncio.sleep", no_sleep)
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await SerpApiProvider(api_key="secret", client=client).search(
        build_flight_query("上海", "新加坡", "2099-08-01")
    )
    await client.aclose()

    assert calls == 2
    assert result.status is ProviderStatus.error
    assert result.error_code == "network"


@pytest.mark.asyncio
async def test_invalid_json_response_is_not_retried():
    calls = 0

    async def handler(request):
        nonlocal calls
        calls += 1
        return httpx.Response(200, content=b"not json")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await SerpApiProvider(api_key="secret", client=client).search(
        build_flight_query("上海", "新加坡", "2099-08-01")
    )
    await client.aclose()

    assert calls == 1
    assert result.status is ProviderStatus.error
    assert result.error_code == "upstream_response"
