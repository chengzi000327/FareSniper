from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

from backend.application.contracts.flight_provider import PriceStatus, ProviderStatus
from backend.application.services.flight_query import build_flight_query
from backend.infrastructure.flight_data.providers.flyai import (
    FlyAIProvider,
    parse_flyai_payload,
)


FIXTURE = Path(__file__).parents[1] / "fixtures/providers/flyai_search_success.json"


def _query():
    return build_flight_query("北京", "上海", "2099-08-01")


def _payload():
    return json.loads(FIXTURE.read_text())


def test_parse_maps_price_flight_and_jump_url():
    offers = parse_flyai_payload(_payload(), _query())

    assert offers[0].data_provider == "flyai"
    assert offers[0].seller_name == "飞猪"
    assert offers[0].total_price == 400
    assert offers[0].base_price is None
    assert offers[0].tax is None
    assert offers[0].baggage_fee is None
    assert offers[0].flight_no == "CA1883"
    assert offers[0].airline == "国航"
    assert offers[0].stops == 0
    assert offers[0].depart_time == "21:00"
    assert offers[0].arrive_time == "23:20"
    assert offers[0].booking_url.startswith("https://")


def test_missing_price_becomes_view_live_price():
    payload = _payload()
    del payload["data"]["itemList"][0]["adultPrice"]

    offer = parse_flyai_payload(payload, _query())[0]

    assert offer.total_price is None
    assert offer.base_price is None
    assert offer.price_status is PriceStatus.view_live_price
    assert offer.booking_url.startswith("https://")


def test_parser_flattens_segments_and_computes_stops():
    payload = _payload()
    payload["data"]["itemList"][0]["journeys"][0]["segments"].append(
        {
            "marketingTransportName": "东航",
            "marketingTransportNo": "MU5100",
            "depDateTime": "2099-08-02 08:00:00",
            "arrDateTime": "2099-08-02 10:00:00",
            "seatClassName": "经济舱",
        }
    )

    offer = parse_flyai_payload(payload, _query())[0]

    assert offer.flight_no == "CA1883/MU5100"
    assert offer.airline == "国航/东航"
    assert offer.stops == 1


def test_parser_skips_unpriced_item_without_valid_https_url():
    payload = _payload()
    payload["data"]["itemList"][0].pop("adultPrice")
    payload["data"]["itemList"][0]["jumpUrl"] = "http://example.com/flight"

    assert parse_flyai_payload(payload, _query()) == []


def test_parser_rejects_non_https_booking_url_but_keeps_numeric_price():
    payload = _payload()
    payload["data"]["itemList"][0]["jumpUrl"] = "http://example.com/flight"

    offer = parse_flyai_payload(payload, _query())[0]

    assert offer.total_price == 400
    assert offer.booking_url is None


@pytest.mark.asyncio
async def test_missing_key_disables_provider():
    result = await FlyAIProvider(api_key="").search(_query())

    assert result.provider == "flyai"
    assert result.status is ProviderStatus.disabled


@pytest.mark.asyncio
async def test_search_uses_safe_arguments_and_inherited_key(monkeypatch):
    calls = []

    class FakeProcess:
        returncode = 0

        async def communicate(self):
            return FIXTURE.read_bytes(), b""

    async def fake_create(*args, **kwargs):
        calls.append((args, kwargs))
        return FakeProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
    result = await FlyAIProvider(api_key="secret", cli_path="/usr/local/bin/flyai").search(
        _query()
    )

    args, kwargs = calls[0]
    assert args == (
        "/usr/local/bin/flyai",
        "search-flight",
        "--origin",
        "北京",
        "--destination",
        "上海",
        "--dep-date",
        "2099-08-01",
        "--sort-type",
        "3",
    )
    assert kwargs["env"]["FLYAI_API_KEY"] == "secret"
    assert kwargs["env"]["PATH"] == os.environ["PATH"]
    assert "secret" not in args
    assert "shell" not in kwargs
    assert result.status is ProviderStatus.success


@pytest.mark.asyncio
async def test_zero_exit_with_upstream_error_status_is_error(monkeypatch):
    class FakeProcess:
        returncode = 0

        async def communicate(self):
            return b'{"status": 401, "data": {"itemList": []}}', b""

    async def fake_create(*args, **kwargs):
        return FakeProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
    result = await FlyAIProvider(api_key="secret").search(_query())

    assert result.status is ProviderStatus.error
    assert result.error_code == "upstream_response"


@pytest.mark.asyncio
async def test_nonzero_exit_classifies_authentication(monkeypatch):
    calls = 0

    class FakeProcess:
        returncode = 1

        async def communicate(self):
            return b"", b"401 unauthorized: api key is invalid"

    async def fake_create(*args, **kwargs):
        nonlocal calls
        calls += 1
        return FakeProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
    result = await FlyAIProvider(api_key="secret").search(_query())

    assert calls == 1
    assert result.status is ProviderStatus.error
    assert result.error_code == "authentication"


@pytest.mark.asyncio
async def test_timeout_kills_process_and_returns_timeout(monkeypatch):
    killed = False
    waited = False

    class FakeProcess:
        returncode = None

        async def communicate(self):
            raise asyncio.TimeoutError

        def kill(self):
            nonlocal killed
            killed = True

        async def wait(self):
            nonlocal waited
            waited = True

    async def fake_create(*args, **kwargs):
        return FakeProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
    result = await FlyAIProvider(api_key="secret", timeout_seconds=0.01).search(_query())

    assert killed is True
    assert waited is True
    assert result.status is ProviderStatus.timeout


@pytest.mark.asyncio
async def test_retries_once_for_transient_network_failure(monkeypatch):
    calls = 0

    class FakeProcess:
        def __init__(self, returncode, stdout, stderr):
            self.returncode = returncode
            self._stdout = stdout
            self._stderr = stderr

        async def communicate(self):
            return self._stdout, self._stderr

    async def fake_create(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return FakeProcess(1, b"", b"connection reset by peer")
        return FakeProcess(0, FIXTURE.read_bytes(), b"")

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
    result = await FlyAIProvider(api_key="secret").search(_query())

    assert calls == 2
    assert result.status is ProviderStatus.success


@pytest.mark.asyncio
async def test_invalid_json_is_error_without_retry(monkeypatch):
    calls = 0

    class FakeProcess:
        returncode = 0

        async def communicate(self):
            return b"not json", b"temporary network failure"

    async def fake_create(*args, **kwargs):
        nonlocal calls
        calls += 1
        return FakeProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
    result = await FlyAIProvider(api_key="secret").search(_query())

    assert calls == 1
    assert result.status is ProviderStatus.error
    assert result.error_code == "invalid_json"
