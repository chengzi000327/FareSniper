from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(ROOT_DIR / ".env")


@dataclass
class Settings:
    app_name: str = os.getenv("APP_NAME", "Flight Deals Backend")
    api_prefix: str = os.getenv("API_PREFIX", "/api")
    default_user_id: str = os.getenv("DEFAULT_USER_ID", "demo-user")
    default_origin: str = os.getenv("DEFAULT_ORIGIN", "BJS")
    database_url: str = os.getenv("DATABASE_URL", "")
    redis_url: str = os.getenv("REDIS_URL", "")

    # LLM 配置：支持两个独立模型，分别用于意图解析和价值判断
    model_base_url: str = os.getenv("MODEL_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")
    model_api_key: str = os.getenv("MODEL_API_KEY", os.getenv("LLM_API_KEY", ""))
    model_intent: str = os.getenv("MODEL_INTENT", "qwen-turbo")
    model_judge: str = os.getenv("MODEL_JUDGE", "qwen-plus")

    # 向后兼容旧环境变量（Railway 老部署可能还用这些）
    llm_provider: str = os.getenv("LLM_PROVIDER", "mock")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
    llm_model: str = os.getenv("LLM_MODEL", "deepseek-chat")

    request_timeout_seconds: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "25"))
    enable_mock_fallback: bool = os.getenv("ENABLE_MOCK_FALLBACK", "true").lower() == "true"
    session_ttl_minutes: int = int(os.getenv("SESSION_TTL_MINUTES", "30"))

    # LangSmith / LangGraph tracing. LangChain reads these from env.
    langchain_tracing: bool = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
    langchain_api_key: str = os.getenv("LANGCHAIN_API_KEY", "")
    langchain_project: str = os.getenv("LANGCHAIN_PROJECT", "faressniper-dev")
    langchain_endpoint: str = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")


settings = Settings()

if settings.langchain_tracing and settings.langchain_api_key:
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_API_KEY", settings.langchain_api_key)
    os.environ.setdefault("LANGCHAIN_PROJECT", settings.langchain_project)
    os.environ.setdefault("LANGCHAIN_ENDPOINT", settings.langchain_endpoint)
