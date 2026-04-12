from __future__ import annotations


class AgentBase:
    """Minimal local fallback for AgentScope's AgentBase."""

    async def reply(self, msg):  # pragma: no cover
        raise NotImplementedError
