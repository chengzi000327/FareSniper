from __future__ import annotations

import asyncio
import json
import os
import signal
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


def test_parser_maps_airport_codes_from_first_and_last_segments():
    offer = parse_flyai_payload(_payload(), _query())[0]

    assert offer.origin_airport_code == "PEK"
    assert offer.destination_airport_code == "PVG"


@pytest.mark.parametrize(
    "scope_update",
    [
        {"origin_airport_scope": "PKX"},
        {"destination_airport_scope": "SHA"},
    ],
)
def test_parser_filters_item_that_conflicts_with_explicit_airport_scope(
    scope_update,
):
    query = _query().model_copy(update=scope_update)

    assert parse_flyai_payload(_payload(), query) == []


def test_parser_normalizes_station_codes_and_falls_back_to_query_airport_scope():
    payload = _payload()
    segment = payload["data"]["itemList"][0]["journeys"][0]["segments"][0]
    segment["depStationCode"] = " invalid "
    segment["arrStationCode"] = None
    query = _query().model_copy(
        update={
            "origin_airport_scope": " pkx ",
            "destination_airport_scope": " sha ",
        }
    )

    offer = parse_flyai_payload(payload, query)[0]

    assert offer.origin_airport_code == "PKX"
    assert offer.destination_airport_code == "SHA"


def test_parser_rejects_non_ascii_station_code_and_uses_query_airport_scope():
    payload = _payload()
    segment = payload["data"]["itemList"][0]["journeys"][0]["segments"][0]
    segment["depStationCode"] = "北京首"
    query = _query().model_copy(update={"origin_airport_scope": "PKX"})

    offer = parse_flyai_payload(payload, query)[0]

    assert offer.origin_airport_code == "PKX"


@pytest.mark.parametrize(
    ("origin_scope", "expected_airport_code"),
    [("PKX", "PKX"), (None, None)],
)
def test_parser_rejects_non_ascii_station_code_before_uppercasing(
    origin_scope,
    expected_airport_code,
):
    payload = _payload()
    segment = payload["data"]["itemList"][0]["journeys"][0]["segments"][0]
    segment["depStationCode"] = "ſha"
    query = _query().model_copy(update={"origin_airport_scope": origin_scope})

    offers = parse_flyai_payload(payload, query)

    assert len(offers) == 1
    assert offers[0].origin_airport_code == expected_airport_code


def test_parser_keeps_none_when_station_codes_and_airport_scopes_are_missing():
    payload = _payload()
    segment = payload["data"]["itemList"][0]["journeys"][0]["segments"][0]
    segment.pop("depStationCode")
    segment.pop("arrStationCode")

    offer = parse_flyai_payload(payload, _query())[0]

    assert offer.origin_airport_code is None
    assert offer.destination_airport_code is None


def test_parser_supports_legacy_adult_price_when_ticket_price_is_absent():
    payload = _payload()
    item = payload["data"]["itemList"][0]
    item["adultPrice"] = "¥410.0"
    item.pop("ticketPrice")

    assert parse_flyai_payload(payload, _query())[0].total_price == 410


def test_parser_prefers_current_ticket_price_over_legacy_adult_price():
    payload = _payload()
    item = payload["data"]["itemList"][0]
    item["ticketPrice"] = "420.00"
    item["adultPrice"] = "999.00"

    assert parse_flyai_payload(payload, _query())[0].total_price == 420


def test_parser_falls_back_to_adult_price_when_ticket_price_is_unusable():
    payload = _payload()
    item = payload["data"]["itemList"][0]
    item["ticketPrice"] = "not available"
    item["adultPrice"] = "¥410.0"

    assert parse_flyai_payload(payload, _query())[0].total_price == 410


def test_parser_keeps_zero_ticket_price_ahead_of_adult_price():
    payload = _payload()
    item = payload["data"]["itemList"][0]
    item["ticketPrice"] = "0"
    item["adultPrice"] = "999.00"

    assert parse_flyai_payload(payload, _query())[0].total_price == 0


def test_missing_price_becomes_view_live_price():
    payload = _payload()
    del payload["data"]["itemList"][0]["ticketPrice"]

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
            "depStationCode": "PVG",
            "arrStationCode": "CAN",
            "depDateTime": "2099-08-02 08:00:00",
            "arrDateTime": "2099-08-02 10:00:00",
            "seatClassName": "经济舱",
        }
    )

    offer = parse_flyai_payload(payload, _query())[0]

    assert offer.flight_no == "CA1883/MU5100"
    assert offer.airline == "国航/东航"
    assert offer.stops == 1
    assert offer.origin_airport_code == "PEK"
    assert offer.destination_airport_code == "CAN"


def test_parser_skips_unpriced_item_without_valid_https_url():
    payload = _payload()
    payload["data"]["itemList"][0].pop("ticketPrice")
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
        "BJS",
        "--destination",
        "SHA",
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
async def test_search_preserves_explicit_airport_in_provider_arguments(monkeypatch):
    calls = []
    payload = _payload()
    payload["data"]["itemList"][0]["journeys"][0]["segments"][0][
        "depStationCode"
    ] = "PKX"

    class FakeProcess:
        returncode = 0

        async def communicate(self):
            return json.dumps(payload).encode(), b""

    async def fake_create(*args, **kwargs):
        calls.append(args)
        return FakeProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
    query = build_flight_query("北京大兴机场", "上海", "2099-08-01")

    result = await FlyAIProvider(api_key="secret").search(query)

    assert calls[0][3:7] == ("PKX", "--destination", "SHA", "--dep-date")
    assert result.status is ProviderStatus.success
    assert result.offers[0].origin_airport_code == "PKX"


@pytest.mark.asyncio
async def test_search_preserves_exact_international_airports(monkeypatch):
    calls = []
    payload = _payload()
    segment = payload["data"]["itemList"][0]["journeys"][0]["segments"][0]
    segment["depStationCode"] = "HND"
    segment["arrStationCode"] = "GMP"

    class FakeProcess:
        returncode = 0

        async def communicate(self):
            return json.dumps(payload).encode(), b""

    async def fake_create(*args, **kwargs):
        calls.append(args)
        return FakeProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
    query = build_flight_query("HND", "GMP", "2099-08-01")

    result = await FlyAIProvider(api_key="secret").search(query)

    assert calls[0][3:7] == ("HND", "--destination", "GMP", "--dep-date")
    assert result.status is ProviderStatus.success
    assert result.offers[0].origin_airport_code == "HND"
    assert result.offers[0].destination_airport_code == "GMP"


@pytest.mark.asyncio
async def test_child_environment_is_a_minimal_allowlist(monkeypatch):
    calls = []
    monkeypatch.setenv("DATABASE_URL", "db-secret-sentinel")
    monkeypatch.setenv("JWT_SECRET", "jwt-secret-sentinel")
    monkeypatch.setenv("SERPAPI_API_KEY", "serp-secret-sentinel")
    monkeypatch.setenv("LANGSMITH_API_KEY", "trace-secret-sentinel")
    monkeypatch.setenv("OPENAI_API_KEY", "model-secret-sentinel")

    class FakeProcess:
        pid = 41001
        returncode = 0

        async def communicate(self):
            return FIXTURE.read_bytes(), b""

    async def fake_create(*args, **kwargs):
        calls.append(kwargs)
        return FakeProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)

    result = await FlyAIProvider(api_key="flyai-key-sentinel").search(_query())

    child_env = calls[0]["env"]
    assert child_env["FLYAI_API_KEY"] == "flyai-key-sentinel"
    assert child_env["PATH"] == os.environ["PATH"]
    assert calls[0]["start_new_session"] is True
    for forbidden in (
        "DATABASE_URL",
        "JWT_SECRET",
        "SERPAPI_API_KEY",
        "LANGSMITH_API_KEY",
        "OPENAI_API_KEY",
    ):
        assert forbidden not in child_env


@pytest.mark.asyncio
async def test_outer_cancellation_kills_process_group_and_awaits_cleanup(
    monkeypatch,
):
    communicate_started = asyncio.Event()
    waited = asyncio.Event()
    killed: list[tuple[int, signal.Signals]] = []

    class FakeProcess:
        pid = 41002
        returncode = None

        async def communicate(self):
            communicate_started.set()
            await asyncio.Event().wait()
            raise AssertionError("unreachable")

        async def wait(self):
            self.returncode = -signal.SIGKILL
            waited.set()
            return self.returncode

    async def fake_create(*args, **kwargs):
        return FakeProcess()

    def fake_killpg(process_group: int, sig: signal.Signals) -> None:
        killed.append((process_group, sig))

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
    monkeypatch.setattr(os, "killpg", fake_killpg)

    task = asyncio.create_task(FlyAIProvider(api_key="key").search(_query()))
    await communicate_started.wait()
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert killed == [(41002, signal.SIGKILL)]
    assert waited.is_set()


@pytest.mark.asyncio
async def test_zero_exit_with_upstream_error_status_is_error(monkeypatch):
    class FakeProcess:
        returncode = 0

        async def communicate(self):
            return b'{"status": 401, "data": {"itemList": []}}', b""

        async def wait(self):
            return self.returncode

    async def fake_create(*args, **kwargs):
        return FakeProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
    result = await FlyAIProvider(api_key="secret").search(_query())

    assert result.status is ProviderStatus.error
    assert result.error_code == "upstream_response"


@pytest.mark.asyncio
async def test_non_object_json_payload_is_upstream_error(monkeypatch):
    class FakeProcess:
        returncode = 0

        async def communicate(self):
            return b"[]", b""

        async def wait(self):
            return self.returncode

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

        async def wait(self):
            return self.returncode

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
async def test_non_auth_non_transient_cli_failure_is_not_retried(monkeypatch):
    calls = 0

    class FakeProcess:
        returncode = 2

        async def communicate(self):
            return b"", b"invalid argument"

        async def wait(self):
            return self.returncode

    async def fake_create(*args, **kwargs):
        nonlocal calls
        calls += 1
        return FakeProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
    result = await FlyAIProvider(api_key="secret").search(_query())

    assert calls == 1
    assert result.status is ProviderStatus.error
    assert result.error_code == "cli_failed"


@pytest.mark.asyncio
async def test_nonzero_exit_kills_process_group_and_awaits_cleanup(monkeypatch):
    killed: list[tuple[int, signal.Signals]] = []
    waited = asyncio.Event()

    class FakeProcess:
        pid = 41003
        returncode = 2

        async def communicate(self):
            return b"", b"invalid argument"

        async def wait(self):
            waited.set()
            return self.returncode

    async def fake_create(*args, **kwargs):
        return FakeProcess()

    def fake_killpg(process_group: int, sig: signal.Signals) -> None:
        killed.append((process_group, sig))

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
    monkeypatch.setattr(os, "killpg", fake_killpg)

    result = await FlyAIProvider(api_key="secret").search(_query())

    assert result.status is ProviderStatus.error
    assert killed == [(41003, signal.SIGKILL)]
    assert waited.is_set()


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

        async def wait(self):
            return self.returncode

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

        async def wait(self):
            return self.returncode

    async def fake_create(*args, **kwargs):
        nonlocal calls
        calls += 1
        return FakeProcess()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
    result = await FlyAIProvider(api_key="secret").search(_query())

    assert calls == 1
    assert result.status is ProviderStatus.error
    assert result.error_code == "invalid_json"
