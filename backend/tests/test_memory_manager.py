"""
Step 4 MemoryManager 测试 — get_full_context 聚合验证
使用 Mock 隔离 ShortTermMemory / LongTermMemory / Summarizer
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.memory.manager import MemoryManager


@pytest.fixture
def mock_stm():
    stm = MagicMock()
    stm.get = AsyncMock(return_value=[
        {"role": "user", "content": "北京到东京"},
        {"role": "assistant", "content": "找到3个航班"},
    ])
    return stm


@pytest.fixture
def mock_ltm():
    ltm = MagicMock()
    ltm.get_preferences = AsyncMock(return_value={
        "price_anchor": 3000,
        "preferred_origins": ["PEK"],
        "cabin_preference": "economy",
    })
    ltm.get_recent_queries = AsyncMock(return_value=[
        {"query_text": "北京到东京", "intent": {"origin": "PEK"}},
    ])
    ltm.get_recent_clicks = AsyncMock(return_value=[])
    return ltm


@pytest.fixture
def mock_summarizer():
    summarizer = MagicMock()
    summarizer.summarize = AsyncMock(return_value="用户关注北京出发、经济舱、预算3000以内的航班。")
    return summarizer


async def test_get_full_context_structure(mock_stm, mock_ltm, mock_summarizer):
    """get_full_context 返回 dict 含 short_term / preferences / long_term_summary。"""
    manager = MemoryManager(mock_stm, mock_ltm, mock_summarizer)
    ctx = await manager.get_full_context("test-user", "sess-1")

    assert "short_term" in ctx
    assert "preferences" in ctx
    assert "long_term_summary" in ctx


async def test_get_full_context_short_term(mock_stm, mock_ltm, mock_summarizer):
    """short_term 包含 stm.get 返回的消息列表。"""
    manager = MemoryManager(mock_stm, mock_ltm, mock_summarizer)
    ctx = await manager.get_full_context("test-user", "sess-1")

    assert len(ctx["short_term"]) == 2
    assert ctx["short_term"][0]["role"] == "user"


async def test_get_full_context_preferences(mock_stm, mock_ltm, mock_summarizer):
    """preferences 包含 ltm.get_preferences 返回的用户偏好。"""
    manager = MemoryManager(mock_stm, mock_ltm, mock_summarizer)
    ctx = await manager.get_full_context("test-user", "sess-1")

    assert ctx["preferences"]["price_anchor"] == 3000
    assert "PEK" in ctx["preferences"]["preferred_origins"]


async def test_get_full_context_no_preferences(mock_stm, mock_ltm, mock_summarizer):
    """ltm 返回 None 时，preferences 为空 dict。"""
    mock_ltm.get_preferences = AsyncMock(return_value=None)
    manager = MemoryManager(mock_stm, mock_ltm, mock_summarizer)
    ctx = await manager.get_full_context("new-user", "sess-1")

    assert ctx["preferences"] == {}


async def test_get_full_context_summary(mock_stm, mock_ltm, mock_summarizer):
    """long_term_summary 来自 summarizer.summarize 的返回。"""
    manager = MemoryManager(mock_stm, mock_ltm, mock_summarizer)
    ctx = await manager.get_full_context("test-user", "sess-1")

    assert "北京" in ctx["long_term_summary"]
