"""
Step 3 LLM Provider 测试
不调用真实 API，全部使用 Mock。
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from backend.llm.providers import PROVIDERS, LLMProviderConfig


# ── 1. LLMProviderConfig 字段验证 ──────────────────────────────────────────


def test_provider_config_fields():
    """每家 Provider 都能构造出完整 config，base_url / model 不为空。"""
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
        assert cfg.timeout == 25.0  # 默认值


def test_provider_config_custom_timeout():
    meta = PROVIDERS["deepseek"]
    cfg = LLMProviderConfig(
        provider="deepseek", api_key="k", base_url=meta["base_url"], model=meta["model"], timeout=10.0
    )
    assert cfg.timeout == 10.0


def test_all_providers_present():
    """默认 provider 清单应包含当前项目支持的全部 provider。"""
    expected = {"deepseek", "siliconflow", "qwen", "glm", "doubao", "minimax", "kimi"}
    assert set(PROVIDERS.keys()) == expected


# ── 2. chat_completion Mock 测试 ────────────────────────────────────────────


async def test_chat_completion_returns_str():
    """Mock httpx → chat_completion 返回字符串。"""
    from backend.llm.client import UnifiedLLMClient

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "北京到东京"}}]
    }

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_http = AsyncMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        client = UnifiedLLMClient(provider="deepseek", api_key="test-key")
        result = await client.chat_completion(
            messages=[{"role": "user", "content": "你好"}]
        )

    assert isinstance(result, str)
    assert result == "北京到东京"


# ── 3. 未知 Provider → ValueError ──────────────────────────────────────────


def test_unknown_provider_raises():
    """构造不存在的 provider 应抛出 ValueError。"""
    from backend.llm.client import UnifiedLLMClient

    with pytest.raises(ValueError, match="unknown provider"):
        UnifiedLLMClient(provider="nonexistent", api_key="k")


# ── 4. 主 Provider 失败 → 自动 fallback ────────────────────────────────────


async def test_fallback_on_primary_failure():
    """主 provider 抛异常时，自动切换到 fallback provider 并返回结果。"""
    from backend.llm.client import UnifiedLLMClient

    call_count = 0

    async def mock_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise Exception("primary failed")
        mock_resp = MagicMock()
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "choices": [{"message": {"content": "fallback ok"}}]
        }
        return mock_resp

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_http = AsyncMock()
        mock_http.post = mock_post
        mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_http)
        mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

        client = UnifiedLLMClient(
            provider="deepseek",
            api_key="test-key",
            fallback_providers=["qwen"],
            fallback_api_keys={"qwen": "qwen-key"},
        )
        result = await client.chat_completion(
            messages=[{"role": "user", "content": "你好"}]
        )

    assert result == "fallback ok"
    assert call_count == 2


# ── 5. mock 模式下 parse_intent / generate_recommendation ─────────────────


async def test_parse_intent_mock_mode():
    """provider=mock 时 parse_intent 返回合法 dict，不调用网络。"""
    from backend.llm.client import UnifiedLLMClient

    client = UnifiedLLMClient(provider="mock", api_key="")
    result = await client.parse_intent("北京到东京下个月去")

    assert "origin" in result
    assert "destination" in result
    assert "date_start" in result
    assert "date_end" in result


async def test_generate_recommendation_mock_mode():
    """provider=mock 时 generate_recommendation 返回合法 dict。"""
    from backend.llm.client import UnifiedLLMClient

    client = UnifiedLLMClient(provider="mock", api_key="")
    result = await client.generate_recommendation(
        flights=[{"price": 2000}],
        preferences={"price_anchor": 3000},
        metrics={"comparison": {}, "history": {}, "preference": {"within_budget": True}, "signals": []},
    )

    assert "recommendation" in result
    assert "confidence" in result
    assert result["confidence"] in ("high", "medium", "low")


async def test_parse_intent_normalizes_llm_payload():
    from backend.llm.client import UnifiedLLMClient

    client = UnifiedLLMClient(provider="mock", api_key="")

    with patch.object(
        client,
        "chat_completion",
        AsyncMock(
            return_value='{"origin":"PEK","destination":"TYO","date_start":"05-01","date_end":"05-05","budget":"3000元"}'
        ),
    ):
        result = await client._parse_intent_via_llm("五一从北京去东京，预算3000以内")

    assert result == {
        "origin": "BJS",
        "destination": "NRT",
        "date_start": "2026-05-01",
        "date_end": "2026-05-05",
        "budget": 3000,
    }


async def test_generate_recommendation_normalizes_llm_payload():
    from backend.llm.client import UnifiedLLMClient

    client = UnifiedLLMClient(provider="mock", api_key="")

    with patch.object(
        client,
        "chat_completion",
        AsyncMock(
            return_value='{"text":"推荐中国国航航班，价格为2199","signals":"低于近90天均价,符合预算","confidence":"0.92"}'
        ),
    ):
        result = await client._generate_recommendation_via_llm([], {}, {})

    assert result == {
        "recommendation": "推荐中国国航航班，价格为2199",
        "signals": ["低于近90天均价", "符合预算"],
        "confidence": "high",
    }


async def test_parse_intent_prefers_explicit_destination_from_text():
    from backend.llm.client import UnifiedLLMClient

    client = UnifiedLLMClient(provider="deepseek", api_key="test-key")

    with patch.object(
        client,
        "_parse_intent_via_llm",
        AsyncMock(
            return_value={
                "origin": "BJS",
                "destination": "SYX",
                "date_start": "2026-05-01",
                "date_end": "2026-05-03",
                "budget": 3000,
            }
        ),
    ):
        result = await client.parse_intent("五一从北京去东京，预算3000以内，帮我看看")

    assert result["origin"] == "BJS"
    assert result["destination"] == "NRT"
    assert result["date_start"] == "2026-05-01"
    assert result["date_end"] == "2026-05-03"
    assert result["budget"] == 3000
