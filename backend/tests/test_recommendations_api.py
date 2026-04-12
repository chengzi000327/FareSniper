"""
Step 8 Recommendations API 测试
"""
from __future__ import annotations

import pytest


async def test_get_recommendations_returns_200(client):
    resp = await client.get("/api/recommendations", params={"user_id": "demo-user"})
    assert resp.status_code == 200


async def test_get_recommendations_schema(client):
    """响应符合 RecommendationsResponseDto 结构。"""
    from backend.schemas.memory import RecommendationsResponseDto

    resp = await client.get("/api/recommendations", params={"user_id": "demo-user"})
    dto = RecommendationsResponseDto.model_validate(resp.json())
    assert dto.user_id == "demo-user"
    assert isinstance(dto.cards, list)


async def test_recommendations_cards_have_required_fields(client):
    """每张卡片含 id / title / reason / query_hint / tags。"""
    resp = await client.get("/api/recommendations", params={"user_id": "demo-user"})
    for card in resp.json()["cards"]:
        assert "id" in card
        assert "title" in card
        assert "reason" in card
        assert "query_hint" in card
        assert "tags" in card
