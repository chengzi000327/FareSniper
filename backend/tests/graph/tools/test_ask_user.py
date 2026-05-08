from __future__ import annotations

import pytest

from backend.application.graph.tools.ask_user import ask_user


@pytest.mark.asyncio
async def test_ask_user_returns_question():
    result = await ask_user.ainvoke(
        {"missing_field": "destination", "context": "已知出发地 BJS"}
    )
    assert "去哪" in result or "目的地" in result
