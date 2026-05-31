from __future__ import annotations

import logging
import time
from pathlib import Path

from backend.config import get_settings

logger = logging.getLogger("faresniper.prompt_loader")

_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"
_CACHE: dict[str, tuple[str, float]] = {}

_DEFAULTS: dict[str, str] = {
    "react_agent": (
        "你是「FareSniper」机票智能助手，帮用户以最快速度找到值得买的机票。\n"
        "根据用户意图调用合适的工具完成槽位补全、搜索、偏好匹配和价值判断；"
        "信息不全时调用 ask_user 每次只问一个缺失项；闲聊直接回复不调用工具。\n"
        "可用动态意图定义：\n{intent_definitions}\n"
        "禁止自己传递 user_id 到 set_alert / get_preferences；该参数由系统注入。"
    ),
}


def _hub_identifier(name: str) -> str:
    prefix = get_settings().langsmith_prompt_prefix
    return f"{prefix}{name.replace('_', '-')}"


def _extract_prompt_text(obj) -> str | None:
    """从 LangSmith pull_prompt 返回对象里提取纯文本（兼容 ChatPromptTemplate / PromptTemplate）。"""
    messages = getattr(obj, "messages", None)
    if messages:
        for m in messages:
            template = getattr(getattr(m, "prompt", None), "template", None)
            if template and "system" in type(m).__name__.lower():
                return template
        first_template = getattr(getattr(messages[0], "prompt", None), "template", None)
        if first_template:
            return first_template
    template = getattr(obj, "template", None)
    return template if isinstance(template, str) else None


def _pull_from_langsmith(name: str) -> str | None:
    s = get_settings()
    if not (s.langchain_api_key or s.langsmith_api_key):
        return None
    try:
        from langsmith import Client

        pulled = Client().pull_prompt(_hub_identifier(name))
        return _extract_prompt_text(pulled)
    except Exception:
        logger.warning("langsmith_pull_failed name=%s", name, exc_info=True)
        return None


def load_prompt(name: str) -> str:
    """优先 LangSmith Hub，回退本地 prompts/*.txt，再回退硬编码默认值；进程内 TTL 缓存。"""
    now = time.monotonic()
    cached = _CACHE.get(name)
    if cached and now - cached[1] < get_settings().prompt_cache_ttl_seconds:
        return cached[0]

    text = _pull_from_langsmith(name)
    if not text:
        path = _PROMPTS_DIR / f"{name}.txt"
        if path.exists():
            text = path.read_text(encoding="utf-8").strip()
    if not text:
        text = _DEFAULTS.get(name, f"You are a helpful assistant. [{name}]")

    _CACHE[name] = (text, now)
    return text
