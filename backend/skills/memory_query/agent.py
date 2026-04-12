from __future__ import annotations

from agentscope.message import Msg

from backend.agents.base import FareSniperAgent


class MemoryQuerySkill(FareSniperAgent):
    """
    从记忆系统读取用户偏好和历史。
    Step 4 的 MemoryManager 接入后替换 stub。
    输出：{"preferences": {...}, "recent_queries": [...]}
    """

    def __init__(self, memory_manager=None) -> None:
        super().__init__()
        self._memory = memory_manager

    async def reply(self, msg: Msg) -> Msg:
        context = msg.metadata if isinstance(msg.metadata, dict) else {}
        user_id = context.get("intent", {}).get("user_id", "demo-user")

        if self._memory is not None:
            try:
                preferences = await self._memory._ltm.get_preferences(user_id) or {}
                recent_queries = await self._memory._ltm.get_recent_queries(user_id, limit=5)
            except Exception:
                preferences, recent_queries = {}, []
        else:
            preferences, recent_queries = {}, []

        import json
        result = {"preferences": preferences, "recent_queries": recent_queries}
        return Msg(
            name="memory_query",
            content=json.dumps(result, ensure_ascii=False),
            role="assistant",
            metadata=result,
        )
