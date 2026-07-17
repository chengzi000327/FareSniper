from __future__ import annotations

import json

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
