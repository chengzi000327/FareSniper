from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parent


@dataclass
class Settings:
    app_name: str = os.getenv("APP_NAME", "Flight Deals Backend")
    api_prefix: str = os.getenv("API_PREFIX", "/api")
    default_user_id: str = os.getenv("DEFAULT_USER_ID", "demo-user")
    default_origin: str = os.getenv("DEFAULT_ORIGIN", "BJS")
    memory_file: Path = Path(os.getenv("MEMORY_FILE", ROOT_DIR / "memory.json"))
    database_url: str = os.getenv("DATABASE_URL", "")
    redis_url: str = os.getenv("REDIS_URL", "")
    llm_provider: str = os.getenv("LLM_PROVIDER", "mock")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://api.deepseek.com")
    llm_model: str = os.getenv("LLM_MODEL", "deepseek-chat")
    request_timeout_seconds: float = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "25"))
    enable_mock_fallback: bool = os.getenv("ENABLE_MOCK_FALLBACK", "true").lower() == "true"


settings = Settings()
