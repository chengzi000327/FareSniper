from __future__ import annotations

import os

from backend.config import get_settings


def langsmith_enabled() -> bool:
    """Return true when runtime tracing has enough config to emit LangSmith runs."""
    settings = get_settings()
    return bool(
        os.getenv("LANGCHAIN_TRACING_V2", "").lower() == "true"
        and (os.getenv("LANGCHAIN_API_KEY") or settings.langsmith_api_key)
    )


def trace_config() -> dict[str, str]:
    """Expose the non-secret LangSmith tracing settings used by health checks/tests."""
    settings = get_settings()
    return {
        "project": os.getenv("LANGCHAIN_PROJECT")
        or settings.langchain_project
        or settings.langsmith_project,
        "endpoint": os.getenv("LANGCHAIN_ENDPOINT")
        or settings.langchain_endpoint
        or settings.langsmith_endpoint,
    }
