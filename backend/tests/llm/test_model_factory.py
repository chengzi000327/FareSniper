from backend.config import get_settings
from backend.infrastructure.llm.models import build_chat_model


def test_agent_role_uses_model_agent_env(monkeypatch):
    monkeypatch.setenv("MODEL_AGENT", "qwen-plus-test")
    monkeypatch.setenv("MODEL_BASE_URL", "https://example/v1")
    monkeypatch.setenv("MODEL_API_KEY", "sk-test")
    get_settings.cache_clear()
    m = build_chat_model(role="agent")
    assert getattr(m, "model", None) == "qwen-plus-test" or getattr(m, "model_name", None) == "qwen-plus-test"
    get_settings.cache_clear()


def test_judge_role_uses_model_judge_env(monkeypatch):
    monkeypatch.setenv("MODEL_JUDGE", "deepseek-chat-test")
    monkeypatch.setenv("MODEL_BASE_URL", "https://example/v1")
    monkeypatch.setenv("MODEL_API_KEY", "sk-test")
    get_settings.cache_clear()
    m = build_chat_model(role="judge")
    assert getattr(m, "model", None) == "deepseek-chat-test" or getattr(m, "model_name", None) == "deepseek-chat-test"
    get_settings.cache_clear()
