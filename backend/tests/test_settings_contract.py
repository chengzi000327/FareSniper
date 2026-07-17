import json
import os
import subprocess
import sys
from types import SimpleNamespace

import pytest

from backend.config import (
    Settings,
    get_settings,
    langsmith_tracing_enabled,
    settings,
)


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


@pytest.mark.parametrize(
    ("tracing", "api_key", "expected"),
    [
        ("false", "ls-test-key", False),
        ("true", "ls-test-key", True),
        ("true", "", False),
        (None, "ls-test-key", False),
    ],
)
def test_langsmith_tracing_requires_explicit_enable_and_key(
    monkeypatch, tracing, api_key, expected
):
    for name in (
        "LANGSMITH_TRACING",
        "LANGCHAIN_TRACING_V2",
        "LANGSMITH_API_KEY",
        "LANGCHAIN_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    if tracing is not None:
        monkeypatch.setenv("LANGSMITH_TRACING", tracing)
    if api_key:
        monkeypatch.setenv("LANGSMITH_API_KEY", api_key)

    runtime_settings = Settings(_env_file=None)

    assert langsmith_tracing_enabled(runtime_settings) is expected


def test_explicit_langsmith_false_overrides_legacy_true(monkeypatch):
    monkeypatch.setenv("LANGSMITH_TRACING", "false")
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGSMITH_API_KEY", "ls-test-key")

    assert langsmith_tracing_enabled(Settings(_env_file=None)) is False


def test_legacy_langchain_flag_cannot_enable_custom_tracing(monkeypatch):
    monkeypatch.delenv("LANGSMITH_TRACING", raising=False)
    monkeypatch.delenv("LANGSMITH_API_KEY", raising=False)
    monkeypatch.setenv("LANGCHAIN_TRACING_V2", "true")
    monkeypatch.setenv("LANGCHAIN_API_KEY", "ls-test-key")

    runtime_settings = SimpleNamespace(
        langsmith_tracing=False,
        langsmith_api_key="",
        langchain_tracing=True,
        langchain_api_key="ls-test-key",
    )

    assert langsmith_tracing_enabled(runtime_settings) is False


def test_config_forces_automatic_tracing_off_but_injects_sdk_settings():
    environment = os.environ.copy()
    environment.update(
        {
            "LANGSMITH_TRACING": "true",
            "LANGSMITH_API_KEY": "ls-test-key",
            "LANGSMITH_PROJECT": "faresniper-test",
            "LANGSMITH_ENDPOINT": "https://langsmith.invalid",
            "LANGCHAIN_TRACING_V2": "true",
            "LANGCHAIN_API_KEY": "legacy-key",
            "LANGCHAIN_PROJECT": "legacy-project",
            "LANGCHAIN_ENDPOINT": "https://legacy.invalid",
        }
    )
    output = subprocess.check_output(
        [
            sys.executable,
            "-c",
            (
                "import json, os; import backend.config; "
                "print(json.dumps({key: os.getenv(key) for key in ("
                "'LANGCHAIN_TRACING_V2', 'LANGCHAIN_API_KEY', "
                "'LANGCHAIN_PROJECT', 'LANGCHAIN_ENDPOINT')}))"
            ),
        ],
        cwd=os.getcwd(),
        env=environment,
        text=True,
    )

    assert json.loads(output) == {
        "LANGCHAIN_TRACING_V2": "false",
        "LANGCHAIN_API_KEY": "ls-test-key",
        "LANGCHAIN_PROJECT": "faresniper-test",
        "LANGCHAIN_ENDPOINT": "https://langsmith.invalid",
    }
