from __future__ import annotations

from typing import Any

from agentscope.message import Msg

from backend.agents.base import FareSniperAgent

# 默认 plan：所有查询都走完整的 4 步流程
DEFAULT_PLAN = ["memory_query", "flight_search", "preference_match", "decision_maker"]


class IntentionAgent(FareSniperAgent):
    """
    Plan 阶段：分析用户意图，输出执行计划。

    content 结构：
    {
        "plan": ["skill_a", "skill_b", ...],
        "intent": {"origin": ..., "destination": ..., ...}
    }
    """

    def __init__(self, llm_client: Any | None = None) -> None:
        super().__init__()
        self._llm = llm_client

    async def reply(self, msg: Msg) -> Msg:
        text = msg.content if isinstance(msg.content, str) else str(msg.content)

        intent = await self._parse_intent(text)
        plan = self._build_plan(intent)

        import json
        return Msg(
            name="intention",
            content=json.dumps({"plan": plan, "intent": intent}, ensure_ascii=False),
            role="assistant",
            metadata={"plan": plan, "intent": intent},
        )

    async def _parse_intent(self, text: str) -> dict[str, Any]:
        if self._llm is not None:
            try:
                return await self._llm.parse_intent(text)
            except Exception:
                pass
        return await self._heuristic_intent(text)

    async def _heuristic_intent(self, text: str) -> dict[str, Any]:
        """无 LLM 时的轻量启发式解析。"""
        return {
            "origin": None,
            "destination": None,
            "depart_date": None,
            "return_date": None,
            "passengers": 1,
            "cabin": "economy",
            "raw": text,
        }

    def _build_plan(self, intent: dict[str, Any]) -> list[str]:
        """根据 intent 决定执行哪些 skill。简单策略：始终走完整链路。"""
        return list(DEFAULT_PLAN)
