from __future__ import annotations

import pytest

import backend.infrastructure.llm.embeddings as emb


@pytest.mark.asyncio
async def test_embed_returns_empty_without_api_key(monkeypatch):
    monkeypatch.setattr(emb.settings, "model_api_key", "")
    assert await emb.embed("北京到上海") == []


@pytest.mark.asyncio
async def test_embed_uses_client(monkeypatch):
    class _Resp:
        data = [type("D", (), {"embedding": [0.1, 0.2, 0.3]})()]

    class _Embeddings:
        async def create(self, **kw):
            return _Resp()

    class _Client:
        embeddings = _Embeddings()

    monkeypatch.setattr(emb.settings, "model_api_key", "sk-x")
    monkeypatch.setattr(emb.settings, "model_base_url", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    monkeypatch.setattr(emb, "_async_client", lambda: _Client())
    assert await emb.embed("北京到上海") == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_embed_skips_deepseek_base_url(monkeypatch):
    monkeypatch.setattr(emb.settings, "model_api_key", "sk-x")
    monkeypatch.setattr(emb.settings, "model_base_url", "https://api.deepseek.com")
    assert await emb.embed("北京到上海") == []
