from __future__ import annotations

import asyncio
import logging
from typing import Any

from agentscope.message import Msg

from backend.agents.base import FareSniperAgent

logger = logging.getLogger(__name__)


class OrchestrationAgent(FareSniperAgent):
    """
    Execute 阶段：按 plan 顺序执行各 skill，聚合结果。

    输入 msg.content 结构（来自 IntentionAgent）：
    {
        "plan": ["skill_a", ...],
        "intent": {...}
    }

    输出 content 结构：
    {
        "skill_a": {...},
        "skill_b": {...},
        ...
    }
    """

    def __init__(self, registry: Any) -> None:
        super().__init__()
        self._registry = registry

    async def reply(self, msg: Msg) -> Msg:
        plan_data = msg.metadata if isinstance(msg.metadata, dict) else {}
        plan: list[str] = plan_data.get("plan", [])
        intent: dict[str, Any] = plan_data.get("intent", {})

        results: dict[str, Any] = {}
        context = {"intent": intent, "results": results}

        for skill_name in plan:
            try:
                skill = self._registry.get(skill_name)
            except KeyError:
                logger.warning("Skill %r not found in registry, skipping.", skill_name)
                continue

            skill_msg = Msg(
                name="orchestrator",
                content="execute",
                role="user",
                metadata=context,
            )
            try:
                response = await skill.reply(skill_msg)
                results[skill_name] = response.metadata if isinstance(response.metadata, dict) else {}
                context = {"intent": intent, "results": results}
            except Exception as exc:
                logger.warning("Skill %r failed: %s", skill_name, exc)
                results[skill_name] = {"error": str(exc)}

        import json
        return Msg(
            name="orchestrator",
            content=json.dumps(results, ensure_ascii=False, default=str),
            role="assistant",
            metadata=results,
        )
