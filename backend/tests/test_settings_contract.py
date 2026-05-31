from backend.config import get_settings, settings


def test_settings_exposes_launch_fields(monkeypatch):
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    monkeypatch.setenv("MODEL_AGENT", "qwen-plus")
    monkeypatch.setenv("LANGSMITH_API_KEY", "lsv2_test")
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    monkeypatch.delenv("LANGCHAIN_API_KEY", raising=False)
    monkeypatch.delenv("LANGCHAIN_TRACING_V2", raising=False)
    get_settings.cache_clear()
    s = get_settings()
    assert s.jwt_secret == "test-secret"
    assert s.model_agent == "qwen-plus"
    assert s.langsmith_api_key == "lsv2_test"
    assert s.langsmith_tracing is True
    assert isinstance(s.cors_origins, list)
    assert hasattr(settings, "database_url")


def test_settings_normalizes_postgres_url_for_async_engine(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@postgres.railway.internal:5432/railway")
    get_settings.cache_clear()
    s = get_settings()
    assert s.database_url.startswith("postgresql+asyncpg://")
