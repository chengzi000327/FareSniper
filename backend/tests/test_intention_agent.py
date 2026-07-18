"""
Step 6 IntentionAgent 测试 — Plan 阶段
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from agentscope.message import Msg

from backend.agents.intention_agent import IntentionAgent


@pytest.fixture
def agent():
    return IntentionAgent(llm_client=None)  # mock 模式


async def test_reply_returns_msg(agent: IntentionAgent):
    """reply 返回 Msg，metadata 含结构化数据。"""
    msg = Msg(name="user", content="帮我找北京到东京的机票", role="user")
    result = await agent.reply(msg)

    assert isinstance(result, Msg)
    assert isinstance(result.metadata, dict)


async def test_plan_contains_skills(agent: IntentionAgent):
    """metadata 包含 plan（list）和 intent（dict）。"""
    msg = Msg(name="user", content="帮我找北京到东京的机票", role="user")
    result = await agent.reply(msg)

    assert "plan" in result.metadata
    assert "intent" in result.metadata
    assert isinstance(result.metadata["plan"], list)
    assert len(result.metadata["plan"]) > 0


async def test_plan_skills_are_valid(agent: IntentionAgent):
    """plan 中的每个 skill 名都是合法的已知 skill。"""
    from backend.skills._registry import KNOWN_SKILLS

    msg = Msg(name="user", content="帮我找北京到东京的机票", role="user")
    result = await agent.reply(msg)

    for skill in result.metadata["plan"]:
        assert skill in KNOWN_SKILLS, f"Unknown skill: {skill}"


async def test_intent_has_required_fields(agent: IntentionAgent):
    """intent dict 必须含当前搜索槽位使用的标准字段。"""
    msg = Msg(name="user", content="北京到东京下个月", role="user")
    result = await agent.reply(msg)

    intent = result.metadata["intent"]
    for field in ("origin", "destination", "depart_date", "return_date"):
        assert field in intent, f"Missing field: {field}"
