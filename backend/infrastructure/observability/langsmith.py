from __future__ import annotations

from backend.config import get_settings, langsmith_tracing_enabled


def langsmith_enabled() -> bool:
    """Return true when runtime tracing has enough config to emit LangSmith runs."""
    return langsmith_tracing_enabled()


def trace_config() -> dict[str, str]:
    """Expose the non-secret LangSmith tracing settings used by health checks/tests."""
    settings = get_settings()
    return {
        "project": settings.langsmith_project,
        "endpoint": settings.langsmith_endpoint,
    }
