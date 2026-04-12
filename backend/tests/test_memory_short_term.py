"""
Step 4 短期记忆测试 — Railway Redis 滑动窗口
"""
from __future__ import annotations

import pytest

from backend.memory.short_term import ShortTermMemory, WINDOW_SIZE, TTL_SECONDS


@pytest.fixture
async def stm(redis_client):
    mem = ShortTermMemory(redis_client)
    yield mem
    try:
        await redis_client.delete("faresniper:chat:test-stm-user")
    except Exception:
        pass


async def test_push_and_get(stm: ShortTermMemory):
    """push 消息后 get 能取到，顺序正确。"""
    await stm.push("test-stm-user", {"role": "user", "content": "你好"})
    await stm.push("test-stm-user", {"role": "assistant", "content": "你好！"})

    msgs = await stm.get("test-stm-user")
    assert len(msgs) == 2
    assert msgs[0]["role"] == "user"
    assert msgs[1]["content"] == "你好！"


async def test_sliding_window(stm: ShortTermMemory):
    """超过 WINDOW_SIZE 条时，旧消息被丢弃，只保留最新 WINDOW_SIZE 条。"""
    for i in range(WINDOW_SIZE + 3):
        await stm.push("test-stm-user", {"role": "user", "content": str(i)})

    msgs = await stm.get("test-stm-user")
    assert len(msgs) == WINDOW_SIZE
    # 最旧的 3 条被丢弃，最新一条是 WINDOW_SIZE+2
    assert msgs[-1]["content"] == str(WINDOW_SIZE + 2)


async def test_ttl_set(stm: ShortTermMemory, redis_client):
    """push 后 key 的 TTL 应在 (0, TTL_SECONDS] 范围内。"""
    await stm.push("test-stm-user", {"role": "user", "content": "ttl test"})
    ttl = await redis_client.ttl("faresniper:chat:test-stm-user")
    assert 0 < ttl <= TTL_SECONDS


async def test_clear(stm: ShortTermMemory):
    """clear 后 get 返回空列表。"""
    await stm.push("test-stm-user", {"role": "user", "content": "hello"})
    await stm.clear("test-stm-user")
    msgs = await stm.get("test-stm-user")
    assert msgs == []
