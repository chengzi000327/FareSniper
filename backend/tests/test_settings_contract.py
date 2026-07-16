from backend.config import Settings, get_settings, settings


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


def test_settings_exposes_flight_provider_defaults(monkeypatch):
    for name in (
        "FLYAI_API_KEY",
        "FLYAI_CLI_PATH",
        "SERPAPI_API_KEY",
        "FLIGHT_PROVIDER_TIMEOUT_SECONDS",
        "CTRIP_SNAPSHOT_TTL_MINUTES",
        "CTRIP_REFRESH_BATCH_SIZE",
        "CTRIP_REQUEST_DELAY_MIN_SECONDS",
        "CTRIP_REQUEST_DELAY_MAX_SECONDS",
        "RUN_SCHEDULER_IN_API",
        "ENABLE_MOCK_FALLBACK",
    ):
        monkeypatch.delenv(name, raising=False)
    s = Settings(_env_file=None)

    assert s.flyai_api_key == ""
    assert s.flyai_cli_path == "flyai"
    assert s.serpapi_api_key == ""
    assert s.flight_provider_timeout_seconds == 10.0
    assert s.ctrip_snapshot_ttl_minutes == 75
    assert s.ctrip_refresh_batch_size == 20
    assert s.ctrip_request_delay_min_seconds == 2.0
    assert s.ctrip_request_delay_max_seconds == 5.0
    assert s.run_scheduler_in_api is False
    assert s.enable_mock_fallback is False
