"""Minimal context envelope assembler for the first SearchGraph migration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ContextEnvelope:
    session_history: list[dict] = field(default_factory=list)
    memory_facts: dict = field(default_factory=dict)
    current_message: str = ""
    assembly_trace: list[str] = field(default_factory=list)


async def assemble_context(
    *,
    session_id: str | None,
    user_id: str,
    message: str,
    session_factory,
    redis_client,
) -> ContextEnvelope:
    history = await _load_session_history(session_id, session_factory)
    memory_facts = await _load_memory_facts(user_id, session_factory)

    return ContextEnvelope(
        session_history=history,
        memory_facts=memory_facts,
        current_message=message,
        assembly_trace=["session_history", "memory_facts", "current_message"],
    )


async def _load_session_history(session_id: str | None, session_factory) -> list[dict]:
    if not session_id or not session_factory:
        return []
    try:
        from sqlalchemy import select

        from backend.db.models import ChatHistory

        async with session_factory() as db:
            stmt = (
                select(ChatHistory)
                .where(ChatHistory.session_id == session_id)
                .order_by(ChatHistory.created_at.asc())
                .limit(10)
            )
            rows = (await db.execute(stmt)).scalars().all()
            return [{"role": r.role, "content": r.content} for r in rows]
    except Exception:
        return []


async def _load_memory_facts(user_id: str, session_factory) -> dict:
    if not session_factory:
        return {}
    try:
        from backend.memory.long_term import LongTermMemory

        async with session_factory() as db:
            return await LongTermMemory(db).get_preferences(user_id) or {}
    except Exception:
        return {}
