"""
Step 1 インフラ接続テスト
Railway PostgreSQL + Redis の疎通を確認する。
"""
from __future__ import annotations

import pytest
import pytest_asyncio


async def test_postgres_connection(db_engine):
    """PostgreSQL に接続して SELECT 1 が返ること。"""
    from sqlalchemy import text

    async with db_engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        row = result.scalar()
    assert row == 1


async def test_redis_connection(redis_client):
    """Redis に接続して SET/GET が正常に動作すること。"""
    key = "faresniper:test:infra"
    await redis_client.set(key, "ok", ex=10)
    value = await redis_client.get(key)
    await redis_client.delete(key)
    assert value == "ok"
