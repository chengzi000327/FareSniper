from __future__ import annotations

import pytest

import backend.api.admin_intents as ai


@pytest.mark.asyncio
async def test_add_example_with_embedding_writes_vector(monkeypatch):
    calls: list[tuple] = []

    async def fake_insert(intent_name, example_text):
        calls.append(("insert", intent_name, example_text))
        return 42

    async def fake_embed(text):
        calls.append(("embed", text))
        return [0.1, 0.2]

    async def fake_set(example_id, vector):
        calls.append(("set", example_id, vector))

    monkeypatch.setattr(ai, "insert_example", fake_insert)
    monkeypatch.setattr(ai, "embed", fake_embed)
    monkeypatch.setattr(ai, "set_example_embedding", fake_set)

    await ai._add_example_with_embedding("search_flight", "北京到上海机票")

    assert calls == [
        ("insert", "search_flight", "北京到上海机票"),
        ("embed", "北京到上海机票"),
        ("set", 42, [0.1, 0.2]),
    ]


@pytest.mark.asyncio
async def test_add_example_with_embedding_skips_empty_vector(monkeypatch):
    calls: list[tuple] = []

    async def fake_insert(intent_name, example_text):
        return 42

    async def fake_embed(text):
        return []

    async def fake_set(example_id, vector):
        calls.append(("set", example_id, vector))

    monkeypatch.setattr(ai, "insert_example", fake_insert)
    monkeypatch.setattr(ai, "embed", fake_embed)
    monkeypatch.setattr(ai, "set_example_embedding", fake_set)

    await ai._add_example_with_embedding("search_flight", "北京到上海机票")

    assert calls == []
