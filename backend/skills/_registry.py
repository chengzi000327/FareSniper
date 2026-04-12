from __future__ import annotations

from typing import TYPE_CHECKING, Type

if TYPE_CHECKING:
    from backend.agents.base import FareSniperAgent

KNOWN_SKILLS = {"flight_search", "preference_match", "decision_maker", "memory_query"}


class LazyAgentRegistry:
    """
    懒加载 Skill 注册表：注册时只存类，第一次 get 时才实例化，之后缓存。
    """

    def __init__(self) -> None:
        self._classes: dict[str, Type[FareSniperAgent]] = {}
        self._instances: dict[str, FareSniperAgent] = {}

    def register(self, name: str, cls: Type[FareSniperAgent]) -> None:
        self._classes[name] = cls

    def get(self, name: str) -> FareSniperAgent:
        if name not in self._classes:
            raise KeyError(f"no-such-skill: {name!r} not registered")
        if name not in self._instances:
            self._instances[name] = self._classes[name]()
        return self._instances[name]


def _build_default_registry() -> LazyAgentRegistry:
    from backend.skills.flight_search.agent import FlightSearchSkill
    from backend.skills.preference_match.agent import PreferenceMatchSkill
    from backend.skills.decision_maker.agent import DecisionMakerSkill
    from backend.skills.memory_query.agent import MemoryQuerySkill

    registry = LazyAgentRegistry()
    registry.register("flight_search", FlightSearchSkill)
    registry.register("preference_match", PreferenceMatchSkill)
    registry.register("decision_maker", DecisionMakerSkill)
    registry.register("memory_query", MemoryQuerySkill)
    return registry


# 模块级单例，延迟构建
_default_registry: LazyAgentRegistry | None = None


def get_default_registry() -> LazyAgentRegistry:
    global _default_registry
    if _default_registry is None:
        _default_registry = _build_default_registry()
    return _default_registry


# 供测试直接引用
@property
def default_registry() -> LazyAgentRegistry:  # type: ignore[misc]
    return get_default_registry()


# 让 `from backend.skills._registry import default_registry` 能用
class _RegistryModule:
    @property
    def default_registry(self) -> LazyAgentRegistry:
        return get_default_registry()


import sys as _sys
_sys.modules[__name__].__class__ = type(
    "_RegistryModule",
    (_RegistryModule, type(_sys.modules[__name__])),
    {},
)
