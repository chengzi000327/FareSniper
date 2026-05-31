from __future__ import annotations

import pytest

import backend.application.services.intent_examples as ie
from backend.application.contracts.intent_registry import IntentDefinition


@pytest.mark.asyncio
async def test_fast_match_returns_intent_above_threshold(monkeypatch):
    async def fake_examples():
        return [
            {
                "id": 1,
                "intent_name": "search_flight",
                "example_text": "北京到上海机票",
                "embedding": [1.0, 0.0],
            }
        ]

    monkeypatch.setattr(ie, "list_examples_with_embeddings", fake_examples)
    monkeypatch.setattr(ie, "embed", lambda text: _coro([1.0, 0.0]))

    match = await ie.fast_intent_match("我要北京飞上海")
    assert match is not None
    assert match["intent_name"] == "search_flight"
    assert match["confidence"] > 0.85


@pytest.mark.asyncio
async def test_fast_match_none_below_threshold(monkeypatch):
    async def fake_examples():
        return [
            {
                "id": 1,
                "intent_name": "search_flight",
                "example_text": "x",
                "embedding": [1.0, 0.0],
            }
        ]

    monkeypatch.setattr(ie, "list_examples_with_embeddings", fake_examples)
    monkeypatch.setattr(ie, "embed", lambda text: _coro([0.0, 1.0]))
    assert await ie.fast_intent_match("天气怎么样") is None


def test_render_intent_definitions():
    defs = [
        IntentDefinition(
            name="search_flight",
            description="查机票",
            required_slots=["origin", "destination", "depart_date"],
            handler_name="search_flights",
        )
    ]
    text = ie.render_intent_definitions(defs)
    assert "search_flight" in text and "查机票" in text


def _coro(v):
    async def _inner():
        return v

    return _inner()
