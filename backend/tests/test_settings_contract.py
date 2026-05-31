from backend.config import get_settings, settings


def test_settings_exposes_launch_fields(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("MODEL_AGENT", "qwen-plus")
    monkeypatch.setenv("LANGSMITH_API_KEY", "lsv2_test")
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
    get_settings.cache_clear()
    s = get_settings()
    assert s.jwt_secret == "test-secret"
    assert s.model_agent == "qwen-plus"
    assert s.langsmith_api_key == "lsv2_test"
    assert isinstance(s.cors_origins, list)
    assert hasattr(settings, "database_url")
