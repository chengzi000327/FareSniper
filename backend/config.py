from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import List

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
    enable_mock_fallback: bool = Field(default=True)
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

    langfuse_public_key: str = Field(default="")
    langfuse_secret_key: str = Field(default="")
    langfuse_host: str = Field(default="https://cloud.langfuse.com")
    langfuse_offline: bool = Field(default=False)

    langsmith_api_key: str = Field(default="")
    langsmith_project: str = Field(default="faresniper-dev")
    langsmith_endpoint: str = Field(
        default="https://api.smith.langchain.com",
        alias="LANGSMITH_ENDPOINT",
    )

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


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()


_trace_api_key = settings.langchain_api_key or settings.langsmith_api_key
_trace_project = (
    os.getenv("LANGCHAIN_PROJECT")
    or os.getenv("LANGSMITH_PROJECT")
    or settings.langchain_project
    or settings.langsmith_project
)
_trace_endpoint = (
    os.getenv("LANGCHAIN_ENDPOINT")
    or os.getenv("LANGSMITH_ENDPOINT")
    or settings.langchain_endpoint
    or settings.langsmith_endpoint
)

if _trace_api_key and (settings.langchain_tracing or settings.langsmith_api_key):
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_API_KEY", _trace_api_key)
    os.environ.setdefault("LANGCHAIN_PROJECT", _trace_project)
    os.environ.setdefault("LANGCHAIN_ENDPOINT", _trace_endpoint)
