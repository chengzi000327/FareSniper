"""IntentParser：使用 MODEL_INTENT 解析用户自然语言意图（PRD 6.1）。"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

from backend.utils.airport_codes import CITY_TO_AIRPORT

_HOLIDAY_MAP = {
    "五一": ("2026-05-01", "2026-05-05"),
    "劳动节": ("2026-05-01", "2026-05-05"),
    "清明": ("2026-04-04", "2026-04-06"),
    "国庆": ("2026-10-01", "2026-10-07"),
    "十一": ("2026-10-01", "2026-10-07"),
    "端午": ("2026-06-19", "2026-06-21"),
    "春节": ("2026-02-17", "2026-02-23"),
    "元旦": ("2026-01-01", "2026-01-01"),
}

_SYSTEM_PROMPT = """你是一个机票查询助手，专注于从用户输入中提取出行意图。

## 任务
从用户输入中提取：origin（出发城市）、destination（目的地）、date_range（出行日期）、budget（预算，未提及则为null）、constraints（约束列表，无则为空数组）。

## 判断逻辑
逐一检查必填字段：
1. origin：是否提到出发城市？"回成都"="成都"，未提及则为null
2. destination：是否有明确目的地？"回家"需结合上下文，无法判断则为null
3. date_range：时间表述转换为具体日期。"五一"=2026-05-01~05-05，"下周末"=最近的周六周日，"清明"=2026-04-04~04-06

## 约束识别
- "不要太早"/"不要红眼" → constraints: ["avoid_redeye"]
- "直飞" → constraints: ["direct_only"]
- "尽量早点到" → constraints: ["prefer_morning"]

## 输出格式
纯JSON，不加代码块，不加解释：
{"origin":"北京","destination":"三亚","date_range":{"start":"2026-05-01","end":"2026-05-05"},"budget":600,"constraints":["avoid_redeye"]}

不确定的字段填null，不要编造。

## 限制
- 城市名用中文，不要转为机场三字码
- 日期统一YYYY-MM-DD格式
- 只输出JSON，没有多余文字"""


class IntentParser:
    def __init__(self, llm_client=None, model: str = "qwen-turbo") -> None:
        self.llm_client = llm_client
        self.model = model

    async def parse(
        self,
        message: str,
        session_history: list[dict[str, str]] | None = None,
    ) -> dict[str, Any]:
        """解析意图，返回结构化字段。缺失必填字段时，对应值为 None。"""
        # 优先用 LLM 解析
        if self.llm_client and getattr(self.llm_client, "_provider", "mock") != "mock":
            result = await self._parse_via_llm(message, session_history or [])
            if result and not result.get("_parse_failed"):
                return self._normalize(result, message)

        # fallback：启发式解析
        return self._parse_heuristic(message)

    async def _parse_via_llm(
        self,
        message: str,
        history: list[dict[str, str]],
    ) -> dict[str, Any] | None:
        messages = [{"role": "system", "content": _SYSTEM_PROMPT}]
        # 最近 4 条历史消息提供上下文
        messages.extend(history[-4:])
        messages.append({"role": "user", "content": message})

        try:
            raw = await self.llm_client.chat_completion(messages)
            extracted = _extract_json(raw)
            parsed = json.loads(extracted)
            return parsed
        except Exception:
            return {"_parse_failed": True}

    def _normalize(self, raw: dict[str, Any], original_text: str) -> dict[str, Any]:
        origin = raw.get("origin")
        destination = raw.get("destination")
        date_range = raw.get("date_range") or {}
        date_start = date_range.get("start") if isinstance(date_range, dict) else None
        date_end = date_range.get("end") if isinstance(date_range, dict) else None

        # 将城市名转为 IATA code
        origin_code = CITY_TO_AIRPORT.get(origin) if origin else None
        dest_code = CITY_TO_AIRPORT.get(destination) if destination else None

        return {
            "origin": origin,
            "origin_code": origin_code,
            "destination": destination,
            "destination_code": dest_code,
            "date_start": date_start,
            "date_end": date_end or date_start,
            "budget": raw.get("budget"),
            "constraints": raw.get("constraints") or [],
            "raw_text": original_text,
            "normalized_text": _build_normalized(origin, destination, date_start, date_end, raw.get("budget")),
            "_parse_failed": raw.get("_parse_failed", False),
        }

    def _parse_heuristic(self, text: str) -> dict[str, Any]:
        origin, origin_code = _extract_city(text, is_origin=True)
        destination, dest_code = _extract_city(text, is_origin=False)
        date_start, date_end = _extract_dates(text)
        budget = _extract_budget(text)
        constraints = _extract_constraints(text)

        return {
            "origin": origin,
            "origin_code": origin_code,
            "destination": destination,
            "destination_code": dest_code,
            "date_start": date_start,
            "date_end": date_end,
            "budget": budget,
            "constraints": constraints,
            "raw_text": text,
            "normalized_text": _build_normalized(origin, destination, date_start, date_end, budget),
            "_parse_failed": False,
        }


def is_intent_complete(intent: dict[str, Any]) -> bool:
    return bool(
        intent.get("origin")
        and intent.get("destination")
        and intent.get("date_start")
    )


# ── helper functions ──────────────────────────────────────────────────────────

def _extract_json(text: str) -> str:
    try:
        json.loads(text.strip())
        return text.strip()
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        return match.group(0) if match else "{}"


def _build_normalized(
    origin: str | None,
    dest: str | None,
    date_start: str | None,
    date_end: str | None,
    budget: int | None,
) -> str:
    budget_text = "预算不限" if budget is None else f"预算≤{budget}"
    return f"{origin or '?'}->{dest or '?'}, {date_start or '?'} 至 {date_end or '?'}, {budget_text}"


def _today() -> date:
    return datetime.now(tz=timezone.utc).date()


def _extract_city(text: str, is_origin: bool) -> tuple[str | None, str | None]:
    if is_origin:
        patterns = [r"从([一-龥]{2,4})出发", r"从([一-龥]{2,4})飞", r"([一-龥]{2,4})出发"]
    else:
        patterns = [r"去([一-龥]{2,4})", r"到([一-龥]{2,4})", r"飞([一-龥]{2,4})"]

    for pat in patterns:
        m = re.search(pat, text)
        if m:
            city = m.group(1)
            code = CITY_TO_AIRPORT.get(city)
            if code:
                return city, code

    # 直接匹配城市名
    for city, code in CITY_TO_AIRPORT.items():
        if city in text:
            return city, code

    return None, None


def _extract_dates(text: str) -> tuple[str | None, str | None]:
    for kw, (start, end) in _HOLIDAY_MAP.items():
        if kw in text:
            return start, end

    full = re.findall(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", text)
    if full:
        parsed = [date(int(y), int(m), int(d)).isoformat() for y, m, d in full]
        return (parsed[0], parsed[0]) if len(parsed) == 1 else (parsed[0], parsed[-1])

    partial = re.findall(r"(\d{1,2})月(\d{1,2})[日号]", text)
    if partial:
        today = _today()
        parsed = [date(today.year, int(m), int(d)).isoformat() for m, d in partial]
        return (parsed[0], parsed[0]) if len(parsed) == 1 else (parsed[0], parsed[-1])

    # 相对日期
    today = _today()
    if "下周末" in text:
        days_ahead = (5 - today.weekday()) % 7 + 7
        sat = today + timedelta(days=days_ahead)
        return sat.isoformat(), (sat + timedelta(days=1)).isoformat()
    if "本周末" in text or "这周末" in text:
        days_ahead = (5 - today.weekday()) % 7
        sat = today + timedelta(days=days_ahead)
        return sat.isoformat(), (sat + timedelta(days=1)).isoformat()

    return None, None


def _extract_budget(text: str) -> int | None:
    for pat in [
        r"(\d+)\s*(?:元)?(?:以内|以下|之内|内)",
        r"预算\s*(\d+)",
        r"不超过\s*(\d+)",
        r"低于\s*(\d+)",
    ]:
        m = re.search(pat, text)
        if m:
            return int(m.group(1))
    return None


def _extract_constraints(text: str) -> list[str]:
    out = []
    if any(kw in text for kw in ["不要太早", "不要红眼", "红眼"]):
        out.append("avoid_redeye")
    if "直飞" in text:
        out.append("direct_only")
    if any(kw in text for kw in ["尽量早点到", "早点到"]):
        out.append("prefer_morning")
    return out
