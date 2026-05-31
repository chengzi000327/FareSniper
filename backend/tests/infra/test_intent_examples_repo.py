from __future__ import annotations

import pytest

from backend.infrastructure.db.base import get_session
from backend.infrastructure.db.intent_registry_repo import (
    IntentExample,
    IntentRegistry,
    list_examples_with_embeddings,
    set_example_embedding,
)


@pytest.mark.asyncio
async def test_set_and_list_embeddings(seeded_pg):
    async with get_session() as s:
        s.add(
            IntentRegistry(
                name="search_flight",
                description="查机票",
                handler_name="search_flights",
            )
        )
        await s.commit()

    async with get_session() as s:
        s.add(
            IntentExample(
                id=1,
                intent_name="search_flight",
                example_text="北京到上海机票",
            )
        )
        await s.commit()

    await set_example_embedding(1, [0.1, 0.2, 0.3])
    rows = await list_examples_with_embeddings()
    assert any(
        r["intent_name"] == "search_flight"
        and r["embedding"] == [0.1, 0.2, 0.3]
        for r in rows
    )
