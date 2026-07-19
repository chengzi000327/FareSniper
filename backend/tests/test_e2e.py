from __future__ import annotations

import copy
from collections.abc import AsyncGenerator
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from backend.application.contracts.intent import DateWindow, LocationRef, NormalizedIntent
from backend.application.contracts.flight_provider import FlightOffer
from backend.application.contracts.decision import FrontendResponse
from backend.application.graph.nodes.render_response import render_response
from backend.application.services.flight_query import build_flight_query
from backend.application.services.flight_search_aggregator import FlightSearchAggregator
from backend.api._deps import current_user_id
from backend.infrastructure.flight_data.providers.ctrip_snapshot import (
    CtripSnapshotProvider,
)
from backend.infrastructure.flight_data.ctrip_parser import parse_batch_search
from backend.main import create_app
from backend.schemas.search import SearchResponseDto


def _now() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class FakeSearchService:
    async def search(self, user_id: str, message: str) -> dict[str, Any]:
        now = _now()
        return {
            "user_id": user_id,
            "query": {
                "raw_text": message,
                "normalized_text": "BJS->SYX, 2099-05-01 至 2099-05-05, 预算≤3000",
                "origin_city": "北京",
                "origin_code": "BJS",
                "destination_city": "三亚",
                "destination_code": "SYX",
                "date_start": "2099-05-01",
                "date_end": "2099-05-05",
                "budget": 3000,
            },
            "deals": [
                {
                    "id": "mock-deal-1",
                    "system_id": "SYS.001",
                    "flight_no": "CA1835",
                    "platform": "ctrip",
                    "origin_city": "北京",
                    "origin_code": "BJS",
                    "destination_city": "三亚",
                    "destination_code": "SYX",
                    "depart_date": "2099-05-01",
                    "airline": "中国国航",
                    "depart_time": "08:00",
                    "arrive_time": "12:00",
                    "price": 2199,
                    "lowest_price": 2199,
                    "total_price": 2199,
                    "currency": "CNY",
                    "winning_price_id": "mock-price-1",
                    "data_freshness": "fresh",
                    "prices": [
                        {
                            "id": "mock-price-1",
                            "name": "ctrip",
                            "price": 2199,
                            "currency": "CNY",
                            "lowest": True,
                            "price_status": "priced",
                            "provider_status": "success",
                            "url": "https://flights.ctrip.com/booking/CA1835",
                            "data_provider": "ctrip_snapshot",
                            "data_freshness": "fresh",
                        }
                    ],
                    "original_price": 2899,
                    "discount_rate": 0.76,
                    "cabin": "economy",
                    "signals": ["低于近90天均价", "符合预算"],
                    "confidence": "high",
                    "verdict": "建议现在买。",
                    "booking_url": "https://flights.ctrip.com/booking/CA1835",
                    "h5_fallback_url": "https://flights.ctrip.com/booking/CA1835",
                }
            ],
            "analysis": {
                "min_price": 2199,
                "max_price": 2450,
                "avg_price": 2324,
                "avg_90d": 2890,
                "lower_than_avg": 0.24,
                "price_spread_pct": 0.11,
                "match_score": 0.92,
                "within_budget": True,
                "matched_preferences": ["东京"],
            },
            "recommendation": {
                "action": "buy_now",
                "text": "建议现在买。当前价格低于近90天均价。",
                "confidence": "high",
                "signals": ["低于近90天均价", "符合预算"],
            },
            "meta": {
                "generated_at": now,
                "source": "ctrip",
                "result_count": 1,
                "fallback_mode": True,
            },
        }


class FakeRecommendationService:
    def __init__(self) -> None:
        self._preferences: dict[str, dict[str, Any]] = {}

    async def get_memory(self, user_id: str) -> dict[str, Any]:
        prefs = self._preferences.get(user_id, {})
        memories = []
        for field, value in prefs.items():
            if value is None:
                continue
            if isinstance(value, list) and not value:
                continue
            memories.append(
                {
                    "id": field,
                    "field": field,
                    "label": field.replace("_", " ").title(),
                    "value": value,
                    "value_display": "、".join(value) if isinstance(value, list) else str(value),
                    "source": "manual",
                    "updated_at": _now(),
                }
            )

        return {
            "user_id": user_id,
            "memories": memories,
            "query_history": [],
            "click_history": [],
            "meta": {"generated_at": _now(), "source": "fake-memory"},
        }

    async def patch_memory(
        self,
        user_id: str,
        field: str,
        value: Any,
        source: str = "manual",
    ) -> dict[str, Any]:
        self._preferences.setdefault(user_id, {})[field] = value
        return await self.get_memory(user_id)

    async def delete_memory_field(self, user_id: str, field: str) -> dict[str, Any]:
        prefs = self._preferences.setdefault(user_id, {})
        prefs.pop(field, None)
        return await self.get_memory(user_id)

    async def get_cards(self, user_id: str) -> dict[str, Any]:
        prefs = self._preferences.get(user_id, {})
        cards = [
            {
                "id": "card-1",
                "title": "热门低价机会",
                "reason": "当前五一东京价格较近90天均价更低。",
                "query_hint": "五一去东京，3000以内",
                "tags": ["热门", "低价"],
                "preview_deal": None,
            }
        ]

        destinations = prefs.get("preferred_destinations") or []
        if destinations:
            cards.append(
                {
                    "id": "card-2",
                    "title": f"猜你会继续关注 {destinations[0]}",
                    "reason": "根据你刚保存的偏好生成",
                    "query_hint": f"去{destinations[0]}，下周末出发",
                    "tags": ["个性化", "记忆"],
                    "preview_deal": None,
                }
            )

        return {
            "user_id": user_id,
            "cards": cards,
            "meta": {
                "generated_at": _now(),
                "source": "fake-recommendations",
                "result_count": len(cards),
            },
        }


@pytest_asyncio.fixture
async def e2e_client() -> AsyncGenerator[AsyncClient, None]:
    app = create_app()
    app.dependency_overrides[current_user_id] = lambda: "demo-user"
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_e2e_flow(e2e_client: AsyncClient) -> None:
    search_payload = await FakeSearchService().search(
        "demo-user", "五一从北京去三亚，预算3000以内，帮我看看"
    )
    graph_output = {
        "response": FrontendResponse.model_validate(search_payload),
        "request_session_id": None,
    }
    with patch("backend.api.search.get_graph") as get_graph:
        get_graph.return_value.ainvoke = AsyncMock(return_value=graph_output)
        search_response = await e2e_client.post(
            "/api/search",
            json={
                "user_id": "demo-user",
                "message": "五一从北京去三亚，预算3000以内，帮我看看",
            },
        )
    assert search_response.status_code == 200
    search_payload = SearchResponseDto.model_validate(search_response.json())
    assert search_payload.query.destination_code == "SYX"
    assert search_payload.recommendation.action in ("buy_now", "watch", "skip")

    with (
        patch("backend.api.memory.list_memories", new=AsyncMock(return_value=[])),
        patch(
            "backend.api.memory.get_user_preferences",
            new=AsyncMock(return_value=None),
        ),
        patch("backend.api.memory.list_query_history", new=AsyncMock(return_value=[])),
    ):
        memory_response = await e2e_client.get("/api/memory")
    assert memory_response.status_code == 200
    assert memory_response.json() == {"memories": [], "query_history": []}

    with patch("backend.api.memory.upsert_memory", new=AsyncMock()) as upsert:
        patch_response = await e2e_client.patch(
            "/api/memory",
            json={
                "field": "preferred_destinations",
                "value": ["东京"],
            },
        )
    assert patch_response.status_code == 200
    assert patch_response.json() == {"ok": True}
    upsert.assert_awaited_once_with(
        "demo-user", "preferred_destinations", ["东京"], source="user"
    )

    with patch("backend.api.memory.delete_field", new=AsyncMock()) as delete:
        delete_response = await e2e_client.delete(
            "/api/memory/preferred_destinations"
        )
    assert delete_response.status_code == 204
    delete.assert_awaited_once_with("demo-user", "preferred_destinations")

    recommendation = {
        "personalized": False,
        "cards": [
            {
                "id": "card-1",
                "title": "热门低价机会",
                "reason": "当前价格较低",
                "tags": ["低价"],
            }
        ],
        "has_more": False,
        "next_offset": 1,
    }
    with patch(
        "backend.api.recommendations.build_recommendations",
        new=AsyncMock(return_value=recommendation),
    ):
        recommendation_response = await e2e_client.get("/api/recommendations")
    assert recommendation_response.status_code == 200
    recommendation_payload = recommendation_response.json()
    assert recommendation_payload["personalized"] is False
    assert recommendation_payload["has_more"] is False
    assert recommendation_payload["next_offset"] == 1
    assert recommendation_payload["cards"][0]["title"] == "热门低价机会"


@pytest.mark.asyncio
async def test_altay_to_sanya_ctrip_snapshot_price_is_grounded_everywhere(
    monkeypatch,
) -> None:
    depart_date = (date.today() + timedelta(days=30)).isoformat()
    query = build_flight_query("阿勒泰", "三亚", depart_date)
    assert query.origin_code == "AAT"
    assert query.destination_code == "SYX"

    stored_rows: list[dict[str, Any]] = []

    async def store_snapshot(offer: FlightOffer) -> None:
        expires_at = (datetime.now(timezone.utc) + timedelta(minutes=75)).isoformat()
        stored_rows.append(
            {
                "flight_no": offer.flight_no,
                "airline": offer.airline,
                "origin_code": offer.origin_code,
                "destination_code": offer.destination_code,
                "depart_date": offer.depart_date,
                "dep_time": offer.depart_time,
                "arr_time": offer.arrive_time,
                "duration": f"{offer.duration_minutes}分钟",
                "stops": offer.stops,
                "prices": [
                    {
                        "platform": "携程",
                        "price": offer.total_price,
                        "currency": "CNY",
                        "url": offer.booking_url,
                        "crawled_at": datetime.now(timezone.utc).isoformat(),
                        "expires_at": expires_at,
                    }
                ],
            }
        )

    async def read_snapshot(**scope):
        matching = [
            row
            for row in stored_rows
            if row["origin_code"] == scope["origin_code"]
            and row["destination_code"] == scope["destination_code"]
            and row["depart_date"] == scope["depart_date"]
        ]
        return matching, 1, False

    monkeypatch.setattr(
        "backend.infrastructure.flight_data.providers.ctrip_snapshot.read_provider_deals",
        read_snapshot,
    )
    await store_snapshot(
        FlightOffer(
            data_provider="ctrip",
            seller_name="携程",
            flight_no="CZ5704",
            airline="南方航空",
            origin_city="阿勒泰",
            origin_code="AAT",
            destination_city="三亚",
            destination_code="SYX",
            depart_date=depart_date,
            depart_time="12:20",
            arrive_time="20:35",
            duration_minutes=495,
            stops=1,
            currency="CNY",
            total_price=1688,
            booking_url=(
                "https://flights.ctrip.com/online/list/oneway-aat-syx"
                f"?depdate={depart_date}&adult=1"
            ),
        )
    )

    search_result = await FlightSearchAggregator(
        [CtripSnapshotProvider()], timeout_seconds=1
    ).collect(query)
    intent = NormalizedIntent(
        origin=LocationRef(city="阿勒泰", iata_code="AAT"),
        destination=LocationRef(city="三亚", iata_code="SYX"),
        date_window=DateWindow(start_date=depart_date, end_date=depart_date),
        raw_text=f"{depart_date} 阿勒泰到三亚",
    )
    rendered = await render_response(
        {
            "request_user_id": "e2e-user",
            "intent": intent,
            "search_result": search_result,
        }
    )
    response = rendered["response"]
    card = response.deals[0]
    ctrip_price = next(
        row["price"]
        for row in card["prices"]
        if row["data_provider"] == "ctrip_snapshot"
    )

    assert ctrip_price == 1688
    assert response.analysis["min_price"] == ctrip_price
    assert f"¥{ctrip_price}" in response.recommendation["text"]
    assert f"CNY {ctrip_price}" in response.recommendation["text"]


@pytest.mark.asyncio
async def test_explicit_airport_capture_filters_before_render(
    monkeypatch,
) -> None:
    depart_date = (date.today() + timedelta(days=30)).isoformat()
    query = build_flight_query(
        "北京大兴机场",
        "上海虹桥机场",
        depart_date,
    )
    fixture_path = (
        Path(__file__).parent / "fixtures/providers/ctrip_batch_search.json"
    )
    payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    pek_itinerary = payload["data"]["flightItineraryList"][0]
    pek_flight = pek_itinerary["flightSegments"][0]["flightList"][0]
    pek_flight["departureDateTime"] = f"{depart_date} 08:00:00"
    pek_flight["arrivalDateTime"] = f"{depart_date} 10:20:00"
    pkx_itinerary = copy.deepcopy(pek_itinerary)
    pkx_flight = pkx_itinerary["flightSegments"][0]["flightList"][0]
    pkx_flight["flightNo"] = "CZ3001"
    pkx_flight["departureAirportCode"] = "PKX"
    payload["data"]["flightItineraryList"] = [pek_itinerary, pkx_itinerary]

    captured = [
        offer.model_copy(
            update={
                "booking_url": (
                    "https://flights.ctrip.com/online/list/oneway-pkx-sha"
                    f"?depdate={depart_date}"
                )
            }
        )
        for offer in parse_batch_search(payload, query)
    ]
    stored_rows = [
        {
            "flight_no": offer.flight_no,
            "airline": offer.airline,
            "origin_code": offer.origin_code,
            "origin_airport_code": offer.origin_airport_code,
            "destination_code": offer.destination_code,
            "destination_airport_code": offer.destination_airport_code,
            "depart_date": offer.depart_date,
            "dep_time": offer.depart_time,
            "arr_time": offer.arrive_time,
            "duration": f"{offer.duration_minutes}分钟",
            "stops": offer.stops,
            "prices": [
                {
                    "platform": "携程",
                    "price": offer.total_price,
                    "currency": "CNY",
                    "url": offer.booking_url,
                    "crawled_at": datetime.now(timezone.utc).isoformat(),
                    "expires_at": (
                        datetime.now(timezone.utc) - timedelta(minutes=1)
                    ).isoformat(),
                }
            ],
        }
        for offer in captured
    ]

    async def read_snapshot(**scope):
        assert scope == {
            "provider": "ctrip_snapshot",
            "origin_code": "BJS",
            "origin_airport_code": "PKX",
            "destination_code": "SHA",
            "destination_airport_code": "SHA",
            "depart_date": depart_date,
        }
        return stored_rows, 1, True

    async def ignore_refresh(**_scope):
        return None

    monkeypatch.setattr(
        "backend.infrastructure.flight_data.providers.ctrip_snapshot.read_provider_deals",
        read_snapshot,
    )
    monkeypatch.setattr(
        "backend.infrastructure.flight_data.providers.ctrip_snapshot.enqueue_demand",
        ignore_refresh,
    )
    search_result = await FlightSearchAggregator(
        [CtripSnapshotProvider()], timeout_seconds=1
    ).collect(query)
    intent = NormalizedIntent(
        origin=LocationRef(city="北京", iata_code="PKX"),
        destination=LocationRef(city="上海", iata_code="SHA"),
        date_window=DateWindow(start_date=depart_date, end_date=depart_date),
        raw_text=f"{depart_date} 北京大兴机场到上海虹桥机场",
    )
    response = (
        await render_response(
            {
                "request_user_id": "e2e-airport-user",
                "intent": intent,
                "search_result": search_result,
            }
        )
    )["response"]

    assert [deal["flight_no"] for deal in response.deals] == ["CZ3001"]
    assert response.deals[0]["origin_code"] == "BJS"
    assert response.deals[0]["origin_airport_code"] == "PKX"
    assert response.deals[0]["destination_code"] == "SHA"
    assert response.deals[0]["destination_airport_code"] == "SHA"
