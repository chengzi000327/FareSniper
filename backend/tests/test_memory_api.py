"""
Step 8 Memory API 测试
"""
from __future__ import annotations

import pytest


async def test_get_memory_returns_200(client):
    resp = await client.get("/api/memory", params={"user_id": "demo-user"})
    assert resp.status_code == 200


async def test_get_memory_schema(client):
    """响应符合 MemoryResponseDto 结构，含 memories 字段。"""
    from backend.schemas.memory import MemoryResponseDto

    resp = await client.get("/api/memory", params={"user_id": "demo-user"})
    dto = MemoryResponseDto.model_validate(resp.json())
    assert dto.user_id == "demo-user"
    assert hasattr(dto, "memories")


async def test_patch_memory(client):
    """PATCH /memory 更新偏好后能读到变更。"""
    resp = await client.patch("/api/memory", json={
        "user_id": "demo-user",
        "field": "price_anchor",
        "value": 3000,
        "source": "manual",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["user_id"] == "demo-user"


async def test_delete_memory_field(client):
    """DELETE /memory/{field} 删除指定偏好字段返回 200。"""
    resp = await client.delete("/api/memory/price_anchor", params={"user_id": "demo-user"})
    assert resp.status_code == 200
