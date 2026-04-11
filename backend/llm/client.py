from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx

from backend.config import Settings


CITY_TO_AIRPORT = {
    "北京": "BJS",
    "上海": "SHA",
    "广州": "CAN",
    "深圳": "SZX",
    "杭州": "HGH",
    "成都": "CTU",
    "重庆": "CKG",
    "三亚": "SYX",
    "昆明": "KMG",
    "厦门": "XMN",
    "西安": "XIY",
    "南京": "NKG",
    "武汉": "WUH",
    "长沙": "CSX",
}

HOLIDAY_RANGES = {
    "五一": ((5, 1), (5, 3)),
    "劳动节": ((5, 1), (5, 3)),
    "国庆": ((10, 1), (10, 7)),
    "十一": ((10, 1), (10, 7)),
    "元旦": ((1, 1), (1, 3)),
}


class LLMClient:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def parse_intent(self, text: str) -> Dict[str, Any]:
        llm_result = await self._parse_intent_via_llm(text)
        if llm_result:
            llm_result.setdefault("raw_text", text)
            llm_result.setdefault("normalized_text", self._build_normalized_text(llm_result))
            return llm_result

        heuristic_result = self._parse_intent_heuristic(text)
        heuristic_result["raw_text"] = text
        heuristic_result["normalized_text"] = self._build_normalized_text(heuristic_result)
        return heuristic_result

    async def generate_recommendation(
        self,
        flights: List[Dict[str, Any]],
        preferences: Dict[str, Any],
        metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        llm_result = await self._generate_recommendation_via_llm(flights, preferences, metrics)
        if llm_result:
            return llm_result
        return self._generate_recommendation_heuristic(metrics)

    async def _parse_intent_via_llm(self, text: str) -> Optional[Dict[str, Any]]:
        if self.settings.llm_provider == "mock" or not self.settings.llm_api_key:
            return None

        prompt = (
            "请把用户机票搜索意图解析成 JSON，字段只允许包含 "
            "origin,destination,date_start,date_end,budget。"
            "如果缺失出发地，请填 BJS。只返回 JSON。用户输入："
            f"{text}"
        )
        content = await self._chat_completion(prompt)
        if not content:
            return None
        try:
            parsed = json.loads(self._extract_json(content))
        except Exception:
            return None
        return {
            "origin": str(parsed.get("origin") or "BJS"),
            "destination": str(parsed.get("destination") or "SYX"),
            "date_start": str(parsed.get("date_start") or self._today().isoformat()),
            "date_end": str(parsed.get("date_end") or self._today().isoformat()),
            "budget": int(parsed["budget"]) if parsed.get("budget") not in (None, "") else None,
        }

    async def _generate_recommendation_via_llm(
        self,
        flights: List[Dict[str, Any]],
        preferences: Dict[str, Any],
        metrics: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        if self.settings.llm_provider == "mock" or not self.settings.llm_api_key:
            return None

        payload = {
            "flights": flights[:3],
            "preferences": preferences,
            "metrics": metrics,
        }
        prompt = (
            "你是机票助手。请基于给定的结构化数据生成 JSON，字段只允许包含 "
            "recommendation,signals,confidence。不要计算新数字。输入："
            f"{json.dumps(payload, ensure_ascii=False)}"
        )
        content = await self._chat_completion(prompt)
        if not content:
            return None
        try:
            parsed = json.loads(self._extract_json(content))
        except Exception:
            return None
        return {
            "recommendation": str(parsed.get("recommendation") or "建议继续观察。"),
            "signals": list(parsed.get("signals") or []),
            "confidence": str(parsed.get("confidence") or "medium"),
        }

    async def _chat_completion(self, prompt: str) -> Optional[str]:
        headers = {
            "Authorization": "Bearer {api_key}".format(api_key=self.settings.llm_api_key),
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.settings.llm_model,
            "messages": [
                {"role": "system", "content": "你是一个严谨的机票搜索助手。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }

        base_url = self.settings.llm_base_url.rstrip("/")
        endpoint = "{base_url}/chat/completions".format(base_url=base_url)

        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout_seconds) as client:
                response = await client.post(endpoint, json=payload, headers=headers)
                response.raise_for_status()
        except Exception:
            return None

        try:
            data = response.json()
            return data["choices"][0]["message"]["content"]
        except Exception:
            return None

    def _parse_intent_heuristic(self, text: str) -> Dict[str, Any]:
        origin = self._extract_origin(text) or self.settings.default_origin
        destination = self._extract_destination(text) or "SYX"
        budget = self._extract_budget(text)
        date_start, date_end = self._extract_dates(text)
        return {
            "origin": origin,
            "destination": destination,
            "date_start": date_start,
            "date_end": date_end,
            "budget": budget,
        }

    def _generate_recommendation_heuristic(self, metrics: Dict[str, Any]) -> Dict[str, Any]:
        comparison = metrics.get("comparison", {})
        history = metrics.get("history", {})
        preference = metrics.get("preference", {})
        signals = list(metrics.get("signals", []))

        lower_than_avg = history.get("lower_than_avg")
        within_budget = preference.get("within_budget")
        match_score = preference.get("match_score", 0.0)
        min_price = comparison.get("min_price")

        if within_budget and isinstance(lower_than_avg, float) and lower_than_avg >= 0.15:
            recommendation = "建议现在买。当前价格低于你的预算，而且相对近90天均价有明显优势。"
            confidence = "high"
        elif within_budget:
            recommendation = "可以考虑入手。当前最低价已经落在你的预算内。"
            confidence = "medium"
        elif match_score >= 0.7 and min_price is not None:
            recommendation = "路线比较符合你的偏好，但当前价格略高，建议继续观察。"
            confidence = "medium"
        else:
            recommendation = "这次先别急着买，继续观察更稳妥。"
            confidence = "low"

        return {
            "recommendation": recommendation,
            "signals": signals,
            "confidence": confidence,
        }

    def _extract_origin(self, text: str) -> Optional[str]:
        match = re.search(r"(?:从|出发地)\s*([一-龥]{2,4})", text)
        if match:
            return CITY_TO_AIRPORT.get(match.group(1))
        return None

    def _extract_destination(self, text: str) -> Optional[str]:
        match = re.search(r"(?:去|到)\s*([一-龥]{2,4})", text)
        if match:
            return CITY_TO_AIRPORT.get(match.group(1))
        for city_name, airport_code in CITY_TO_AIRPORT.items():
            if city_name in text and airport_code != self.settings.default_origin:
                return airport_code
        return None

    def _extract_budget(self, text: str) -> Optional[int]:
        patterns = [
            r"(\d+)\s*(?:元)?(?:以内|以下|之内|内)",
            r"预算\s*(\d+)",
            r"不超过\s*(\d+)",
            r"低于\s*(\d+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return int(match.group(1))
        return None

    def _extract_dates(self, text: str) -> Tuple[str, str]:
        for keyword, date_range in HOLIDAY_RANGES.items():
            if keyword in text:
                current_year = self._today().year
                start = date(current_year, date_range[0][0], date_range[0][1]).isoformat()
                end = date(current_year, date_range[1][0], date_range[1][1]).isoformat()
                return start, end

        full_dates = re.findall(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", text)
        if full_dates:
            parsed_dates = [date(int(year), int(month), int(day)).isoformat() for year, month, day in full_dates]
            if len(parsed_dates) == 1:
                return parsed_dates[0], parsed_dates[0]
            return parsed_dates[0], parsed_dates[1]

        partial_dates = re.findall(r"(\d{1,2})月(\d{1,2})日", text)
        if partial_dates:
            current_year = self._today().year
            parsed_dates = [date(current_year, int(month), int(day)).isoformat() for month, day in partial_dates]
            if len(parsed_dates) == 1:
                return parsed_dates[0], parsed_dates[0]
            return parsed_dates[0], parsed_dates[1]

        default_start = self._today().isoformat()
        default_end = (self._today()).isoformat()
        return default_start, default_end

    def _build_normalized_text(self, parsed: Dict[str, Any]) -> str:
        budget_text = "预算不限" if parsed.get("budget") is None else "预算≤{budget}".format(budget=parsed["budget"])
        return "{origin}->{destination}, {start} 至 {end}, {budget}".format(
            origin=parsed.get("origin", "BJS"),
            destination=parsed.get("destination", "SYX"),
            start=parsed.get("date_start", ""),
            end=parsed.get("date_end", ""),
            budget=budget_text,
        )

    @staticmethod
    def _extract_json(content: str) -> str:
        match = re.search(r"\{.*\}", content, flags=re.S)
        return match.group(0) if match else content

    @staticmethod
    def _today() -> date:
        return datetime.utcnow().date()
