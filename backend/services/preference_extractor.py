"""从用户对话中异步提取显式偏好（预算/偏好航司/常去城市/出行习惯）。

不在主链路决策上，由 render_response 在响应生成后异步调用。
复用现有 build_chat_model（线上配置的 qwen/deepseek），失败静默。
"""
from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger("faresniper.preference_extractor")

_EXTRACT_PROMPT = """你是机票助手的记忆模块。从用户这句话里提取**长期出行偏好**，只提取用户明确表达的，不要猜测。

返回严格的 JSON，字段如下（没有就省略该字段，不要编造）：
- budget: 整数，用户提到的预算/心理价位（人民币元），如"预算600"→600
- preferred_airlines: 字符串数组，用户表达喜欢/偏好的航司，如"我喜欢东航"→["东方航空"]
- frequent_cities: 字符串数组，用户提到常去/喜欢的目的地城市（仅当明确表达"常去""经常飞"等长期偏好时，单次出行查询不算）
- constraints: 字符串数组，出行习惯，可选值："avoid_redeye"(不要红眼航班)、"direct_only"(只要直飞)、"morning"(偏好上午)、"prefer_window"(靠窗)等

用户这句话："{message}"

只返回 JSON，不要任何解释。如果完全没有可提取的长期偏好，返回 {{}}。"""


async def extract_preferences_from_message(message: str) -> dict[str, Any]:
    """调 LLM 提取偏好，返回规范化 dict（可能为空）。失败返回 {}。"""
    if not message or not message.strip():
        return {}
    try:
        from backend.infrastructure.llm.models import build_chat_model

        model = build_chat_model(role="intent")
        prompt = _EXTRACT_PROMPT.format(message=message.strip())
        resp = await model.ainvoke(prompt)
        content = getattr(resp, "content", "") or ""
        if isinstance(content, list):  # 某些模型返回 content blocks
            content = "".join(
                b.get("text", "") if isinstance(b, dict) else str(b) for b in content
            )
        data = _parse_json(content)
        return _sanitize(data)
    except Exception:
        logger.warning("preference_extract_failed", exc_info=True)
        return {}


def _parse_json(text: str) -> dict[str, Any]:
    text = text.strip()
    # 去掉可能的 ```json ``` 包裹
    if text.startswith("```"):
        text = text.split("```", 2)[1] if "```" in text[3:] else text[3:]
        if text.startswith("json"):
            text = text[4:]
    try:
        data = json.loads(text.strip())
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, ValueError):
        # 尝试截取第一个 { 到最后一个 }
        start, end = text.find("{"), text.rfind("}")
        if 0 <= start < end:
            try:
                data = json.loads(text[start : end + 1])
                return data if isinstance(data, dict) else {}
            except (json.JSONDecodeError, ValueError):
                return {}
        return {}


def _sanitize(data: dict[str, Any]) -> dict[str, Any]:
    """只保留合法字段和类型，过滤垃圾。"""
    out: dict[str, Any] = {}
    budget = data.get("budget")
    if isinstance(budget, (int, float)) and 0 < budget < 1_000_000:
        out["budget"] = int(budget)
    for key in ("preferred_airlines", "frequent_cities", "constraints"):
        val = data.get(key)
        if isinstance(val, list):
            cleaned = [str(v).strip() for v in val if str(v).strip()]
            if cleaned:
                out[key] = cleaned
    return out


async def learn_preferences(user_id: str, message: str, session_factory) -> None:
    """提取偏好并合并写入 user_preferences（数组字段累积去重，budget 覆盖）。"""
    if not session_factory or not user_id:
        return
    extracted = await extract_preferences_from_message(message)
    if not extracted:
        return
    try:
        async with session_factory() as db:
            from backend.memory.long_term import LongTermMemory

            ltm = LongTermMemory(db)
            existing = await ltm.get_preferences(user_id) or {}
            merged: dict[str, Any] = {}

            if "budget" in extracted:
                merged["budget"] = extracted["budget"]
            for key in ("preferred_airlines", "frequent_cities", "constraints"):
                if key in extracted:
                    current = list(existing.get(key) or [])
                    for v in extracted[key]:
                        if v not in current:
                            current.append(v)
                    merged[key] = current

            if merged:
                await ltm.upsert_preferences(user_id, merged)
                await db.commit()
                logger.info(
                    "preferences_learned user_id=%s fields=%s",
                    user_id,
                    sorted(merged.keys()),
                )
    except Exception:
        logger.warning("preferences_write_failed user_id=%s", user_id, exc_info=True)
