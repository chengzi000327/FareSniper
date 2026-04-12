"""
Step 6 OrchestrationAgent 测试 — Execute 阶段
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from agentscope.message import Msg

from backend.agents.orchestration_agent import OrchestrationAgent
from backend.skills._registry import LazyAgentRegistry


@pytest.fixture
def mock_registry():
    """每个 skill 返回固定 mock 结果。"""
    registry = LazyAgentRegistry()

    def make_skill(name, result_content):
        import json
        from backend.agents.base import FareSniperAgent

        class MockSkill(FareSniperAgent):
            async def reply(self, msg):
                return Msg(
                    name=name,
                    content=json.dumps(result_content, ensure_ascii=False),
                    role="assistant",
                    metadata=result_content,
                )

        return MockSkill

    registry.register("flight_search", make_skill("flight_search", {"deals": [{"price": 2580}]}))
    registry.register("preference_match", make_skill("preference_match", {"match_score": 0.8}))
    registry.register("decision_maker", make_skill("decision_maker", {"action": "buy_now", "text": "建议购买"}))
    registry.register("memory_query", make_skill("memory_query", {"preferences": {}}))
    return registry


@pytest.fixture
def agent(mock_registry):
    return OrchestrationAgent(registry=mock_registry)


def _plan_msg(plan, intent=None):
    import json
    if intent is None:
        intent = {"origin": "PEK", "destination": "NRT", "date_start": "2026-05-01", "date_end": "2026-05-03"}
    data = {"plan": plan, "intent": intent}
    return Msg(
        name="intention",
        content=json.dumps(data, ensure_ascii=False),
        role="assistant",
        metadata=data,
    )


async def test_execute_plan_returns_msg(agent: OrchestrationAgent):
    """execute_plan 返回 Msg，metadata 包含各 skill 结果。"""
    result = await agent.reply(_plan_msg(["flight_search", "preference_match", "decision_maker"]))

    assert isinstance(result, Msg)
    assert isinstance(result.metadata, dict)


async def test_all_skills_results_present(agent: OrchestrationAgent):
    """每个 skill 的输出都出现在最终 metadata 中。"""
    result = await agent.reply(_plan_msg(["flight_search", "preference_match", "decision_maker"]))

    assert "flight_search" in result.metadata
    assert "preference_match" in result.metadata
    assert "decision_maker" in result.metadata


async def test_unknown_skill_is_skipped(agent: OrchestrationAgent):
    """plan 中包含未注册的 skill 时，跳过该 skill，不影响其他结果。"""
    result = await agent.reply(_plan_msg(["flight_search", "unknown_skill"]))

    assert "flight_search" in result.metadata
    assert "unknown_skill" not in result.metadata
