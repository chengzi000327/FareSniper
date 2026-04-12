from __future__ import annotations

from agentscope.message import Msg

from backend.agents.base import FareSniperAgent


class FlightSearchSkill(FareSniperAgent):
    """
    搜索航班数据。
    输入：context dict（含 intent）
    输出：{"deals": [...]}
    Step 7 接入真实数据源后填充。
    """

    async def reply(self, msg: Msg) -> Msg:
        context = msg.metadata if isinstance(msg.metadata, dict) else {}
        intent = context.get("intent", {})

        import json
        result = {"deals": [], "intent_echo": intent}
        return Msg(
            name="flight_search",
            content=json.dumps(result, ensure_ascii=False),
            role="assistant",
            metadata=result,
        )
