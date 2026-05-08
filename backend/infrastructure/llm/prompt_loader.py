from __future__ import annotations

from pathlib import Path

_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"

_DEFAULTS: dict[str, str] = {
    "react_agent": (
        "你是 FareSniper 机票助手。根据用户意图调用合适的工具完成搜索、偏好匹配和价值判断。"
        "禁止自己传递 user_id 参数到 set_alert / get_preferences 工具；这两个工具的 user_id 由系统注入。"
    ),
}


def load_prompt(name: str) -> str:
    """Load a prompt template by name from the prompts/ directory, falling back to defaults."""
    path = _PROMPTS_DIR / f"{name}.txt"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return _DEFAULTS.get(name, f"You are a helpful assistant. [{name}]")
