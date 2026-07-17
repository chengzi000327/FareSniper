from __future__ import annotations

import json
import subprocess
import sys

import pytest


@pytest.fixture
def smoke_module():
    from backend.scripts import verify_flight_providers

    return verify_flight_providers


def test_smoke_uses_real_aggregator_contract_and_prints_safe_summary(
    monkeypatch, capsys, smoke_module
):
    secret = "SMOKE_SECRET_SENTINEL"
    booking_url = f"https://booking.example/checkout?token={secret}"
    captured = {}
    providers = [object()]

    class FakeAggregator:
        def __init__(self, configured_providers, *, timeout_seconds):
            captured["providers"] = configured_providers
            captured["timeout_seconds"] = timeout_seconds

        async def collect(self, query):
            captured["query"] = query
            return {
                "provider_statuses": {
                    "flyai": "success",
                    "ctrip": "queued",
                },
                "deals": [
                    {
                        "platform": "飞猪",
                        "booking_url": booking_url,
                        "prices": [
                            {"name": "飞猪", "url": booking_url},
                            {"name": "携程", "url": booking_url},
                        ],
                    }
                ],
                "errors": {"flyai": secret},
            }

    monkeypatch.setattr(smoke_module, "build_flight_providers", lambda: providers)
    monkeypatch.setattr(smoke_module, "FlightSearchAggregator", FakeAggregator)

    exit_code = smoke_module.main(
        [
            "--origin",
            "北京",
            "--destination",
            "上海",
            "--depart-date",
            "2099-08-01",
        ]
    )

    output = capsys.readouterr().out
    assert exit_code == 0
    assert json.loads(output) == {
        "provider_statuses": {"flyai": "success", "ctrip": "queued"},
        "deal_count": 1,
        "sellers": ["携程", "飞猪"],
    }
    assert captured["providers"] is providers
    assert captured["query"].origin_city == "北京"
    assert captured["query"].destination_city == "上海"
    assert secret not in output
    assert booking_url not in output


@pytest.mark.parametrize(
    ("origin", "destination", "depart_date"),
    [
        ("BJS", "上海", "2099-08-01"),
        ("北京", "SHA", "2099-08-01"),
        ("北京", "上海", "2099-8-1"),
        ("北京", "上海", "2020-01-01"),
    ],
)
def test_smoke_rejects_noncanonical_query_without_running_providers(
    monkeypatch,
    capsys,
    smoke_module,
    origin,
    destination,
    depart_date,
):
    monkeypatch.setattr(
        smoke_module,
        "build_flight_providers",
        lambda: pytest.fail("providers must not be built for invalid input"),
    )

    exit_code = smoke_module.main(
        [
            "--origin",
            origin,
            "--destination",
            destination,
            "--depart-date",
            depart_date,
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert json.loads(captured.out) == {
        "provider_statuses": {},
        "deal_count": 0,
        "sellers": [],
    }
    assert "Traceback" not in captured.err


def test_smoke_failure_omits_exception_text_and_traceback(
    monkeypatch, capsys, smoke_module
):
    secret = "FAILURE_SECRET_SENTINEL"

    class FailingAggregator:
        def __init__(self, providers, *, timeout_seconds):
            pass

        async def collect(self, query):
            raise RuntimeError(
                f"provider failed with {secret} at https://booking.example/private"
            )

    monkeypatch.setattr(smoke_module, "build_flight_providers", lambda: [object()])
    monkeypatch.setattr(smoke_module, "FlightSearchAggregator", FailingAggregator)

    exit_code = smoke_module.main(
        [
            "--origin",
            "上海",
            "--destination",
            "新加坡",
            "--depart-date",
            "2099-08-01",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert json.loads(captured.out) == {
        "provider_statuses": {},
        "deal_count": 0,
        "sellers": [],
    }
    assert secret not in captured.out + captured.err
    assert "booking.example" not in captured.out + captured.err
    assert "Traceback" not in captured.err


@pytest.mark.parametrize(
    "seller",
    [
        "https://seller.example",
        "www.seller.example",
        "sk-sensitive-value",
        "lsv2_sensitive_value",
        "api_key",
        "token seller",
        "secret seller",
        "auth provider",
        "Bearer credential",
        "seller=value",
        "seller?query",
        "seller/path",
        r"seller\path",
        "seller@example",
        "seller:443",
        "a" * 64,
        "0123456789abcdef" * 4,
    ],
)
def test_smoke_omits_sensitive_seller_shapes(seller, smoke_module):
    summary = smoke_module._safe_summary(
        {
            "provider_statuses": {"flyai": "success"},
            "deals": [
                {
                    "platform": seller,
                    "prices": [
                        {"name": seller},
                        {"name": "Singapore Airlines"},
                        {"name": "中国国际航空"},
                    ],
                }
            ],
        }
    )

    assert summary["sellers"] == ["Singapore Airlines", "中国国际航空"]


@pytest.mark.parametrize(
    "seller",
    [
        "A1B2C3D4E5F6",
        "0123456789abcdefABCD",
        "eyJhbGciOiJIUzI1NiJ9.abc123.signature",
        "https://seller.example/path",
    ],
)
def test_safe_seller_rejects_unconfirmed_or_opaque_values(seller, smoke_module):
    assert smoke_module._safe_seller(seller) is None


@pytest.mark.parametrize(
    ("seller", "expected"),
    [
        ("飞猪", "飞猪"),
        ("携程", "携程"),
        ("Trip.com", "Trip.com"),
        ("Google Flights", "Google Flights"),
        ("  Singapore   Airlines  ", "Singapore Airlines"),
        ("Partner Air", "Partner Air"),
        ("Air France", "Air France"),
        ("中国国际航空", "中国国际航空"),
    ],
)
def test_safe_seller_normalizes_confirmed_platform_and_airline_names(
    seller, expected, smoke_module
):
    assert smoke_module._safe_seller(seller) == expected


@pytest.mark.parametrize(
    "arguments",
    [
        [
            "--origin",
            "北京",
            "--destination",
            "上海",
            "--depart-date",
            "2099-08-01",
            "--unknown-provider-argument",
            "https://private.example/path?token=ARG_SECRET_SENTINEL",
        ],
        [
            "--origin",
            "https://private.example/path?token=ARG_SECRET_SENTINEL",
            "--destination",
            "上海",
            "--depart-date",
        ],
    ],
)
def test_smoke_argument_errors_never_echo_unknown_values(arguments):
    injected = "https://private.example/path?token=ARG_SECRET_SENTINEL"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "backend.scripts.verify_flight_providers",
            *arguments,
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 2
    assert json.loads(result.stdout) == {
        "provider_statuses": {},
        "deal_count": 0,
        "sellers": [],
    }
    assert result.stderr == "Flight provider smoke check rejected invalid arguments.\n"
    assert injected not in result.stdout + result.stderr
    assert "ARG_SECRET_SENTINEL" not in result.stdout + result.stderr


def test_smoke_omits_configured_secret_and_secret_substrings(
    monkeypatch, capsys, smoke_module
):
    configured_key = "AlphaBetaCredential987654321"
    compare_calls = []
    original_compare = smoke_module.hmac.compare_digest

    def capture_compare(left, right):
        compare_calls.append((left, right))
        return original_compare(left, right)

    monkeypatch.setattr(smoke_module.hmac, "compare_digest", capture_compare)
    monkeypatch.setattr(smoke_module.settings, "model_api_key", configured_key)

    summary = smoke_module._safe_summary(
        {
            "provider_statuses": {"flyai": "success"},
            "deals": [
                {
                    "platform": configured_key,
                    "prices": [
                        {"name": f"Airline {configured_key} Partner"},
                        {"name": "中国国际航空"},
                    ],
                }
            ],
        }
    )
    smoke_module._print_summary(summary)

    output = capsys.readouterr().out
    assert summary["sellers"] == ["中国国际航空"]
    assert configured_key not in output
    assert compare_calls


@pytest.mark.parametrize(
    "provider_statuses",
    [
        {},
        {"flyai": "error"},
        {"flyai": "timeout", "ctrip": "queued"},
        {"flyai": "disabled", "ctrip": "stale", "serpapi": "error"},
    ],
)
def test_smoke_returns_failure_when_no_provider_succeeds(
    monkeypatch, capsys, smoke_module, provider_statuses
):
    async def fake_run(origin, destination, depart_date):
        return {
            "provider_statuses": provider_statuses,
            "deal_count": 0,
            "sellers": [],
        }

    monkeypatch.setattr(smoke_module, "_run", fake_run)

    exit_code = smoke_module.main(
        [
            "--origin",
            "北京",
            "--destination",
            "上海",
            "--depart-date",
            "2099-08-01",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 1
    assert set(json.loads(captured.out)) == {
        "provider_statuses",
        "deal_count",
        "sellers",
    }
    assert captured.err == "Flight provider smoke check found no usable provider.\n"


@pytest.mark.parametrize("terminal_status", ["success", "empty"])
def test_smoke_returns_success_for_usable_terminal_provider(
    monkeypatch, capsys, smoke_module, terminal_status
):
    async def fake_run(origin, destination, depart_date):
        return {
            "provider_statuses": {
                "flyai": terminal_status,
                "ctrip": "error",
            },
            "deal_count": 0,
            "sellers": [],
        }

    monkeypatch.setattr(smoke_module, "_run", fake_run)

    exit_code = smoke_module.main(
        [
            "--origin",
            "北京",
            "--destination",
            "上海",
            "--depart-date",
            "2099-08-01",
        ]
    )

    assert exit_code == 0
    assert capsys.readouterr().err == ""
