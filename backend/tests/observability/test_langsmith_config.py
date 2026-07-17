from backend.infrastructure.observability import langsmith


def test_health_flag_reuses_custom_tracing_helper(monkeypatch):
    calls = []
    monkeypatch.setattr(
        langsmith,
        "langsmith_tracing_enabled",
        lambda: calls.append("called") or True,
    )

    assert langsmith.langsmith_enabled() is True
    assert calls == ["called"]


def test_trace_config_uses_langsmith_settings_not_legacy_aliases(monkeypatch):
    class RuntimeSettings:
        langsmith_project = "faresniper-safe"
        langsmith_endpoint = "https://langsmith.invalid"

    monkeypatch.setattr(langsmith, "get_settings", lambda: RuntimeSettings())
    monkeypatch.setenv("LANGCHAIN_PROJECT", "unsafe-legacy-project")
    monkeypatch.setenv("LANGCHAIN_ENDPOINT", "https://legacy.invalid")

    assert langsmith.trace_config() == {
        "project": "faresniper-safe",
        "endpoint": "https://langsmith.invalid",
    }
