from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List

from langsmith import configure as configure_langsmith
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parent
ENV_FILE = ROOT_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        env_prefix="",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = Field(default="FareSniper Backend")
    api_prefix: str = Field(default="/api")
    default_user_id: str = Field(default="demo-user")
    default_origin: str = Field(default="BJS")

    cors_origins: List[str] = Field(
        default_factory=lambda: ["https://faresniper.app", "http://localhost:3000"]
    )

    database_url: str = Field(default="")
    test_database_url: str = Field(default="")
    redis_url: str = Field(default="")

    model_base_url: str = Field(default="https://dashscope.aliyuncs.com/compatible-mode/v1")
    model_api_key: str = Field(default="")
    model_intent: str = Field(default="qwen-turbo")
    model_judge: str = Field(default="qwen-plus")
    model_agent: str = Field(default="qwen-plus")
    model_thinking: str = Field(default="disabled")

    llm_provider: str = Field(default="mock")
    llm_api_key: str = Field(default="")
    llm_base_url: str = Field(default="https://api.deepseek.com")
    llm_model: str = Field(default="deepseek-chat")

    request_timeout_seconds: float = Field(default=25.0)
    flyai_api_key: str = Field(default="")
    flyai_cli_path: str = Field(default="flyai")
    serpapi_api_key: str = Field(default="")
    flight_provider_timeout_seconds: float = Field(default=10.0)
    ctrip_snapshot_ttl_minutes: int = Field(default=75)
    ctrip_refresh_batch_size: int = Field(default=20)
    ctrip_collection_timeout_seconds: float = Field(default=90.0, gt=0)
    ctrip_request_delay_min_seconds: float = Field(default=2.0)
    ctrip_request_delay_max_seconds: float = Field(default=5.0)
    run_scheduler_in_api: bool = Field(default=False)
    enable_mock_fallback: bool = Field(default=False)
    scraper_playwright_enabled: bool = Field(default=False)
    session_ttl_minutes: int = Field(default=30)

    jwt_secret: str = Field(default="")
    jwt_algorithm: str = Field(default="HS256")
    jwt_expires_minutes: int = Field(default=60 * 24 * 30)

    sms_provider: str = Field(default="aliyun")
    sms_aliyun_endpoint: str = Field(default="https://dysmsapi.aliyuncs.com")
    sms_aliyun_access_key_id: str = Field(default="")
    sms_twilio_sid: str = Field(default="")
    sms_twilio_token: str = Field(default="")
    sms_twilio_from: str = Field(default="")

    vapid_private_key: str = Field(default="")
    vapid_public_key: str = Field(default="")
    vapid_subject: str = Field(default="mailto:ops@faresniper.app")

    flight_status_api_url: str = Field(default="")
    flight_status_api_key: str = Field(default="")

    cps_id_default: str = Field(default="")

    variflight_api_key: str = Field(default="")

    langsmith_api_key: str = Field(default="")
    langsmith_project: str = Field(default="faresniper-dev")
    langsmith_endpoint: str = Field(
        default="https://api.smith.langchain.com",
        alias="LANGSMITH_ENDPOINT",
    )
    faresniper_langsmith_tracing: bool = Field(
        default=False,
        alias="FARESNIPER_LANGSMITH_TRACING",
    )
    langsmith_prompt_prefix: str = Field(default="faresniper-")
    prompt_cache_ttl_seconds: float = Field(default=300.0)

    langchain_tracing: bool = Field(default=False, alias="LANGCHAIN_TRACING_V2")
    langchain_api_key: str = Field(default="", alias="LANGCHAIN_API_KEY")
    langchain_project: str = Field(default="faresniper-dev", alias="LANGCHAIN_PROJECT")
    langchain_endpoint: str = Field(default="https://api.smith.langchain.com", alias="LANGCHAIN_ENDPOINT")

    @field_validator("cors_origins", mode="before")
    @classmethod
    def _split_cors(cls, v):
        if v is None or v == "":
            return []
        if isinstance(v, str):
            stripped = v.strip()
            if stripped.startswith("["):
                import json

                return json.loads(stripped)
            return [item.strip() for item in stripped.split(",") if item.strip()]
        return v

    @field_validator("database_url", "test_database_url", mode="before")
    @classmethod
    def _normalize_async_database_url(cls, v):
        if not isinstance(v, str):
            return v
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        return v


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def _environment_flag(name: str) -> bool | None:
    value = os.getenv(name)
    if value is None:
        return None
    normalized = value.strip().casefold()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    return None


def langsmith_tracing_enabled(
    runtime_settings: Settings | None = None,
) -> bool:
    current = runtime_settings or get_settings()
    explicit_langsmith = _environment_flag("FARESNIPER_LANGSMITH_TRACING")
    requested = (
        explicit_langsmith
        if explicit_langsmith is not None
        else current.faresniper_langsmith_tracing
    )
    api_key = os.getenv("LANGSMITH_API_KEY") or current.langsmith_api_key
    return bool(requested and api_key)


_trace_api_key = os.getenv("LANGSMITH_API_KEY") or settings.langsmith_api_key
_trace_project = (
    os.getenv("LANGSMITH_PROJECT") or settings.langsmith_project
)
_trace_endpoint = (
    os.getenv("LANGSMITH_ENDPOINT") or settings.langsmith_endpoint
)

os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LANGCHAIN_TRACING_V2"] = "false"
configure_langsmith(enabled=False)
if _trace_api_key:
    os.environ["LANGCHAIN_API_KEY"] = _trace_api_key
os.environ["LANGCHAIN_PROJECT"] = _trace_project
os.environ["LANGCHAIN_ENDPOINT"] = _trace_endpoint
