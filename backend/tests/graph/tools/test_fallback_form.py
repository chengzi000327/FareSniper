from __future__ import annotations

import pytest

from backend.application.graph.tools.fallback_form import fallback_form


@pytest.mark.asyncio
async def test_returns_modal_directive():
    out = await fallback_form.ainvoke({"reason": "clarify_exceeded"})
    assert out["ui"] == "modal"
    assert out["fields"] == ["origin", "destination", "depart_date", "budget"]
    assert out["reason"] == "clarify_exceeded"


@pytest.mark.asyncio
async def test_optional_user_id_emits_event(seeded_pg):
    """传入 user_id 时同步写 fallback_triggered 事件。"""
    out = await fallback_form.ainvoke(
        {"reason": "clarify_exceeded", "user_id": "u1"}
    )
    assert out["reason"] == "clarify_exceeded"
    from backend.analytics.events import EventName
    from backend.infrastructure.db.event_repo import count_events

    assert await count_events(EventName.FALLBACK_TRIGGERED, user_id="u1") == 1
