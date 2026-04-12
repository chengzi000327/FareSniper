from __future__ import annotations

from agentscope.agent import AgentBase
from agentscope.message import Msg


class FareSniperAgent(AgentBase):
    """FareSniper 所有 Agent/Skill 的基类。"""

    async def reply(self, msg: Msg) -> Msg:  # type: ignore[override]
        raise NotImplementedError
