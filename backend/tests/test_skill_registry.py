"""
Step 6 LazyAgentRegistry 测试
"""
from __future__ import annotations

import pytest

from backend.skills._registry import LazyAgentRegistry


def test_register_and_get():
    """注册 skill 后能通过名字拿到实例。"""
    from backend.agents.base import FareSniperAgent

    registry = LazyAgentRegistry()

    class DummySkill(FareSniperAgent):
        async def reply(self, msg):
            from agentscope.message import Msg
            return Msg(name="dummy", content="ok", role="assistant")

    registry.register("dummy", DummySkill)
    agent = registry.get("dummy")
    assert isinstance(agent, DummySkill)


def test_lazy_instantiation():
    """同名 skill 多次 get 返回同一实例（懒加载后缓存）。"""
    from backend.agents.base import FareSniperAgent

    registry = LazyAgentRegistry()

    class DummySkill2(FareSniperAgent):
        async def reply(self, msg):
            from agentscope.message import Msg
            return Msg(name="dummy2", content="ok", role="assistant")

    registry.register("dummy2", DummySkill2)
    a1 = registry.get("dummy2")
    a2 = registry.get("dummy2")
    assert a1 is a2


def test_unknown_skill_raises():
    """未注册的 skill 名应抛出 KeyError。"""
    registry = LazyAgentRegistry()
    with pytest.raises(KeyError, match="no-such-skill"):
        registry.get("no-such-skill")


def test_all_four_skills_registered():
    """默认 registry 应包含 4 个核心 skill。"""
    from backend.skills._registry import default_registry

    expected = {"flight_search", "preference_match", "decision_maker", "memory_query"}
    assert expected.issubset(set(default_registry._classes.keys()))
