from __future__ import annotations

import importlib

import pytest

from backend.application.graph.tools.search_flights import search_flights
from backend.application.services.flight_query import build_flight_query
from backend.application.services.search_events import (
    SearchEventEmitter,
    bind_search_event_emitter,
)
from backend.infrastructure.flight_data.providers.factory import (
    build_flight_providers,
)


def test_tool_preserves_name_and_exact_three_arguments():
    schema = search_flights.args_schema.model_json_schema()

    assert search_flights.name == "search_flights"
    assert list(schema["properties"]) == [
        "origin",
        "destination",
        "depart_date",
    ]
    assert schema["required"] == ["origin", "destination", "depart_date"]


def test_factory_order_and_serpapi_domestic_exclusion():
    providers = build_flight_providers()

    assert [provider.name for provider in providers] == [
        "flyai",
        "ctrip",
        "serpapi",
    ]
    domestic = build_flight_query("北京", "上海", "2099-08-01")
    international = build_flight_query("上海", "新加坡", "2099-08-01")
    assert providers[-1].supports(domestic) is False
    assert providers[-1].supports(international) is True


@pytest.mark.asyncio
async def test_validation_error_returns_deterministic_result_and_event(monkeypatch):
    module = importlib.import_module(
        "backend.application.graph.tools.search_flights"
    )
    events: list[dict] = []

    def unexpected_factory():
        raise AssertionError("providers must not be built for invalid input")

    monkeypatch.setattr(module, "build_flight_providers", unexpected_factory)

    with bind_search_event_emitter(SearchEventEmitter("validation", events.append)):
        result = await search_flights.ainvoke(
            {
                "origin": "北京",
                "destination": "上海",
                "depart_date": "not-a-date",
            }
        )

    assert result == {
        "deals": [],
        "source": "validation_error",
        "provider_statuses": {},
        "validation_error": "出发日期必须使用 YYYY-MM-DD",
    }
    assert [event["type"] for event in events] == ["validation_error"]
    assert events[0]["payload"] == {
        "message": "出发日期必须使用 YYYY-MM-DD"
    }


@pytest.mark.asyncio
async def test_tool_delegates_to_real_aggregator_with_settings_timeout(monkeypatch):
    module = importlib.import_module(
        "backend.application.graph.tools.search_flights"
    )
    providers = [object()]
    captured: dict = {}
    expected = {
        "deals": [],
        "source": "multi_provider",
        "provider_statuses": {},
        "errors": {},
    }

    class FakeAggregator:
        def __init__(self, actual_providers, *, timeout_seconds):
            captured["providers"] = actual_providers
            captured["timeout_seconds"] = timeout_seconds

        async def collect(self, query):
            captured["query"] = query
            return expected

    monkeypatch.setattr(module, "build_flight_providers", lambda: providers)
    monkeypatch.setattr(module, "FlightSearchAggregator", FakeAggregator)

    result = await search_flights.ainvoke(
        {
            "origin": "北京",
            "destination": "上海",
            "depart_date": "2099-08-01",
        }
    )

    assert result == expected
    assert captured["providers"] is providers
    assert (
        captured["timeout_seconds"]
        == module.settings.flight_provider_timeout_seconds
        == 10.0
    )
    assert captured["query"].origin_code == "BJS"
    assert captured["query"].destination_code == "SHA"
