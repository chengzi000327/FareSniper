"""
LLM Provider 配置测试（仅覆盖 backend.llm.providers；
UnifiedLLMClient 已在 TG-19 随 backend/llm/client.py 一起下线）
"""
from __future__ import annotations

from backend.llm.providers import PROVIDERS, LLMProviderConfig


def test_provider_config_fields():
    for name, meta in PROVIDERS.items():
        cfg = LLMProviderConfig(
            provider=name,
            api_key="test-key",
            base_url=meta["base_url"],
            model=meta["model"],
        )
        assert cfg.provider == name
        assert cfg.base_url.startswith("https://")
        assert cfg.model
        assert cfg.timeout == 25.0


def test_provider_config_custom_timeout():
    meta = PROVIDERS["deepseek"]
    cfg = LLMProviderConfig(
        provider="deepseek", api_key="k", base_url=meta["base_url"], model=meta["model"], timeout=10.0
    )
    assert cfg.timeout == 10.0


def test_all_providers_present():
    expected = {"deepseek", "siliconflow", "qwen", "glm", "doubao", "minimax", "kimi"}
    assert set(PROVIDERS.keys()) == expected
