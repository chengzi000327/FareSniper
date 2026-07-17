from __future__ import annotations

import json
from pathlib import Path

from backend.scripts.generate_flight_wire_fixture import build_fixture_events


FIXTURE = (
    Path(__file__).parents[3]
    / "frontend"
    / "__tests__"
    / "fixtures"
    / "backend-progressive-search.ndjson"
)


def test_committed_frontend_fixture_matches_backend_progressive_payload() -> None:
    committed = [
        json.loads(line)
        for line in FIXTURE.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert committed == build_fixture_events()


def test_backend_fixture_preserves_https_deep_link_query_and_currency() -> None:
    events = build_fixture_events()
    result_deal = next(
        event["payload"]["deals"][0]
        for event in events
        if event["type"] == "results"
    )

    assert result_deal["recommend_score"] is None
    assert result_deal["currency"] == "CNY"
    assert {row["currency"] for row in result_deal["prices"]} == {"CNY", "USD"}
    assert {row["price_status"] for row in result_deal["prices"]} == {"priced"}
    assert {row["provider_status"] for row in result_deal["prices"]} == {
        "success"
    }
    assert any(
        row["url"].endswith("?offer=fixture-token-not-secret&channel=web")
        for row in result_deal["prices"]
    )
