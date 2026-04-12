"""
Step 8 Search API 测试
"""
from __future__ import annotations

import pytest


async def test_search_returns_200(client):
    resp = await client.post("/api/search", json={"user_id": "demo-user", "message": "北京到三亚"})
    assert resp.status_code == 200


async def test_search_response_schema(client):
    """响应符合 SearchResponseDto 结构。"""
    from backend.schemas.search import SearchResponseDto

    resp = await client.post("/api/search", json={"user_id": "demo-user", "message": "北京到三亚"})
    dto = SearchResponseDto.model_validate(resp.json())
    assert dto.user_id == "demo-user"
    assert isinstance(dto.deals, list)
    assert dto.recommendation.action in ("buy_now", "watch", "skip")


async def test_search_deals_have_required_fields(client):
    """deals 列表中每条都有 system_id / origin_city / destination_city / confidence / verdict。"""
    resp = await client.post("/api/search", json={"user_id": "demo-user", "message": "北京到三亚"})
    data = resp.json()
    for deal in data["deals"]:
        assert "system_id" in deal
        assert "origin_city" in deal
        assert "destination_city" in deal
        assert "confidence" in deal
        assert "verdict" in deal


async def test_search_missing_message(client):
    """缺少 message 字段返回 422。"""
    resp = await client.post("/api/search", json={"user_id": "demo-user"})
    assert resp.status_code == 422
