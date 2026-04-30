from __future__ import annotations

from collections.abc import AsyncGenerator
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

from backend.application.contracts.intent import DateWindow, LocationRef, NormalizedIntent
from backend.main import create_app
from backend.schemas.memory import MemoryResponseDto, RecommendationsResponseDto
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
                "normalized_text": "BJS->NRT, 2026-05-01 至 2026-05-05, 预算≤3000",
                "origin_city": "北京",
                "origin_code": "BJS",
                "destination_city": "东京",
                "destination_code": "NRT",
                "date_start": "2026-05-01",
                "date_end": "2026-05-05",
                "budget": 3000,
            },
            "deals": [
                {
                    "id": "mock-deal-1",
                    "system_id": "SYS.001",
                    "platform": "ctrip",
                    "origin_city": "北京",
                    "origin_code": "BJS",
                    "destination_city": "东京",
                    "destination_code": "NRT",
                    "depart_date": "2026-05-01",
                    "airline": "中国国航",
                    "depart_time": "08:00",
                    "arrive_time": "12:00",
                    "price": 2199,
                    "original_price": 2899,
                    "discount_rate": 0.76,
                    "cabin": "economy",
                    "signals": ["低于近90天均价", "符合预算"],
                    "confidence": "high",
                    "verdict": "建议现在买。",
                    "booking_url": None,
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
    async with LifespanManager(app, startup_timeout=30) as manager:
        app.state.search_service = FakeSearchService()
        app.state.recommendation_service = FakeRecommendationService()
        transport = ASGITransport(app=manager.app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest.mark.asyncio
async def test_e2e_flow(e2e_client: AsyncClient) -> None:
    complete_intent = NormalizedIntent(
        origin=LocationRef(city="北京", iata_code="BJS"),
        destination=LocationRef(city="三亚", iata_code="SYX"),
        date_window=DateWindow(start_date="2026-05-01", end_date="2026-05-05"),
        budget_cny=3000,
        parse_failed=False,
    )
    with patch("backend.application.graph.nodes.parse_intent._intent_chain") as mock:
        mock.ainvoke = AsyncMock(return_value=complete_intent)
        search_response = await e2e_client.post(
            "/api/search",
            json={"user_id": "demo-user", "message": "五一从北京去三亚，预算3000以内，帮我看看"},
        )
    assert search_response.status_code == 200
    search_payload = SearchResponseDto.model_validate(search_response.json())
    assert search_payload.query.destination_code == "SYX"
    assert search_payload.recommendation.action in ("buy_now", "watch", "skip")

    memory_response = await e2e_client.get("/api/memory", params={"user_id": "demo-user"})
    assert memory_response.status_code == 200
    memory_payload = MemoryResponseDto.model_validate(memory_response.json())
    assert memory_payload.user_id == "demo-user"
    assert memory_payload.memories == []

    patch_response = await e2e_client.patch(
        "/api/memory",
        json={
            "user_id": "demo-user",
            "field": "preferred_destinations",
            "value": ["东京"],
            "source": "manual",
        },
    )
    assert patch_response.status_code == 200
    patch_payload = MemoryResponseDto.model_validate(patch_response.json())
    assert any(item.field == "preferred_destinations" for item in patch_payload.memories)

    delete_response = await e2e_client.delete(
        "/api/memory/preferred_destinations",
        params={"user_id": "demo-user"},
    )
    assert delete_response.status_code == 200
    delete_payload = MemoryResponseDto.model_validate(delete_response.json())
    assert all(item.field != "preferred_destinations" for item in delete_payload.memories)

    recommendation_response = await e2e_client.get(
        "/api/recommendations",
        params={"user_id": "demo-user"},
    )
    assert recommendation_response.status_code == 200
    recommendation_payload = RecommendationsResponseDto.model_validate(recommendation_response.json())
    assert recommendation_payload.user_id == "demo-user"
    assert len(recommendation_payload.cards) >= 1
