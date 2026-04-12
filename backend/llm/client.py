from __future__ import annotations

import json
import re
from datetime import date, datetime
from typing import Any, Optional

import httpx

from backend.llm.providers import PROVIDERS, LLMProviderConfig
from backend.resilience.circuit_breaker import CircuitBreaker
from backend.utils.airport_codes import CITY_TO_AIRPORT

HOLIDAY_RANGES = {
    "五一": ((5, 1), (5, 3)),
    "劳动节": ((5, 1), (5, 3)),
    "国庆": ((10, 1), (10, 7)),
    "十一": ((10, 1), (10, 7)),
    "元旦": ((1, 1), (1, 3)),
}

LOCATION_ALIASES = {
    "beijing": "BJS",
    "pek": "BJS",
    "pkx": "BJS",
    "shanghai": "SHA",
    "sha": "SHA",
    "pvg": "SHA",
    "guangzhou": "CAN",
    "can": "CAN",
    "chengdu": "CTU",
    "ctu": "CTU",
    "tokyo": "NRT",
    "tyo": "NRT",
    "hnd": "NRT",
    "nrt": "NRT",
    "seoul": "ICN",
    "sel": "ICN",
    "icn": "ICN",
    "hongkong": "HKG",
    "hkg": "HKG",
    "singapore": "SIN",
    "sin": "SIN",
    "bangkok": "BKK",
    "bkk": "BKK",
    "kualalumpur": "KUL",
    "kul": "KUL",
    "sanya": "SYX",
    "syx": "SYX",
    "北京": "BJS",
    "上海": "SHA",
    "广州": "CAN",
    "成都": "CTU",
    "东京": "NRT",
    "首尔": "ICN",
    "香港": "HKG",
    "新加坡": "SIN",
    "曼谷": "BKK",
    "吉隆坡": "KUL",
    "三亚": "SYX",
}


class UnifiedLLMClient:
    def __init__(
        self,
        provider: str,
        api_key: str,
        *,
        model: str | None = None,
        base_url: str | None = None,
        timeout: float = 25.0,
        fallback_providers: list[str] | None = None,
        fallback_api_keys: dict[str, str] | None = None,
        default_origin: str = "BJS",
    ) -> None:
        if provider != "mock" and provider not in PROVIDERS:
            raise ValueError(f"unknown provider: {provider!r}. Valid: {list(PROVIDERS)}")

        self._provider = provider
        self._api_key = api_key
        self._default_origin = default_origin

        if provider != "mock":
            meta = PROVIDERS[provider]
            self._config = LLMProviderConfig(
                provider=provider,
                api_key=api_key,
                base_url=base_url or meta["base_url"],
                model=model or meta["model"],
                timeout=timeout,
            )
        else:
            self._config = None

        # fallback chain
        self._fallback_providers = fallback_providers or []
        self._fallback_api_keys = fallback_api_keys or {}

        # 每个 provider 独立熔断器（5 次失败 → 开路，30s 后试探）
        self._circuit_breakers: dict[str, CircuitBreaker] = {}

    # ── Public API ────────────────────────────────────────────────────────

    async def chat_completion(
        self,
        messages: list[dict[str, str]],
        provider: str | None = None,
        temperature: float = 0.2,
    ) -> str:
        """向 LLM 发送消息，返回回复字符串。失败时自动 fallback。"""
        configs = self._build_config_chain(provider)
        last_error: Exception | None = None

        for cfg in configs:
            try:
                return await self._call(cfg, messages, temperature)
            except Exception as e:
                last_error = e
                continue

        raise RuntimeError(f"All providers failed. Last error: {last_error}")

    async def parse_intent(self, text: str) -> dict[str, Any]:
        """解析用户意图，mock 模式下走启发式解析。"""
        heuristic = self._parse_intent_heuristic(text)
        if self._provider == "mock" or not self._api_key:
            return heuristic

        llm_result = await self._parse_intent_via_llm(text)
        if llm_result:
            result = self._merge_intent_with_heuristic(llm_result, heuristic)
            result.setdefault("raw_text", text)
            result.setdefault("normalized_text", self._build_normalized_text(result))
            return result

        fallback = heuristic
        fallback["raw_text"] = text
        fallback["normalized_text"] = self._build_normalized_text(fallback)
        return fallback

    async def generate_recommendation(
        self,
        flights: list[dict[str, Any]],
        preferences: dict[str, Any],
        metrics: dict[str, Any],
    ) -> dict[str, Any]:
        """生成推荐，mock 模式下走启发式。"""
        if self._provider == "mock" or not self._api_key:
            return self._generate_recommendation_heuristic(metrics)

        result = await self._generate_recommendation_via_llm(flights, preferences, metrics)
        return result or self._generate_recommendation_heuristic(metrics)

    # ── Internal ──────────────────────────────────────────────────────────

    def _build_config_chain(self, override_provider: str | None) -> list[LLMProviderConfig]:
        configs: list[LLMProviderConfig] = []

        if override_provider and override_provider != self._provider:
            if override_provider not in PROVIDERS:
                raise ValueError(f"unknown provider: {override_provider!r}")
            meta = PROVIDERS[override_provider]
            configs.append(LLMProviderConfig(
                provider=override_provider,
                api_key=self._fallback_api_keys.get(override_provider, self._api_key),
                base_url=meta["base_url"],
                model=meta["model"],
                timeout=self._config.timeout if self._config else 25.0,
            ))
        elif self._config:
            configs.append(self._config)

        for name in self._fallback_providers:
            if name in PROVIDERS:
                meta = PROVIDERS[name]
                configs.append(LLMProviderConfig(
                    provider=name,
                    api_key=self._fallback_api_keys.get(name, self._api_key),
                    base_url=meta["base_url"],
                    model=meta["model"],
                    timeout=self._config.timeout if self._config else 25.0,
                ))

        return configs

    def _get_circuit_breaker(self, provider: str) -> CircuitBreaker:
        if provider not in self._circuit_breakers:
            self._circuit_breakers[provider] = CircuitBreaker(
                failure_threshold=5, recovery_timeout=30.0
            )
        return self._circuit_breakers[provider]

    async def _call(
        self,
        cfg: LLMProviderConfig,
        messages: list[dict[str, str]],
        temperature: float,
    ) -> str:
        cb = self._get_circuit_breaker(cfg.provider)

        async def _do_call() -> str:
            headers = {
                "Authorization": f"Bearer {cfg.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": cfg.model,
                "messages": messages,
                "temperature": temperature,
            }
            endpoint = f"{cfg.base_url.rstrip('/')}/chat/completions"
            async with httpx.AsyncClient(timeout=cfg.timeout) as client:
                response = await client.post(endpoint, json=payload, headers=headers)
                response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

        return await cb.call(_do_call)

    async def _parse_intent_via_llm(self, text: str) -> dict[str, Any] | None:
        prompt = (
            "请把用户机票搜索意图解析成 JSON，字段只允许包含 "
            "origin,destination,date_start,date_end,budget。"
            "如果缺失出发地，请填 BJS。只返回 JSON。用户输入："
            f"{text}"
        )
        try:
            content = await self.chat_completion(
                messages=[
                    {"role": "system", "content": "你是一个严谨的机票搜索助手。"},
                    {"role": "user", "content": prompt},
                ]
            )
            parsed = json.loads(self._extract_json(content))
        except Exception:
            return None

        return self._normalize_intent_payload(parsed)

    async def _generate_recommendation_via_llm(
        self,
        flights: list[dict[str, Any]],
        preferences: dict[str, Any],
        metrics: dict[str, Any],
    ) -> dict[str, Any] | None:
        payload = {"flights": flights[:3], "preferences": preferences, "metrics": metrics}
        prompt = (
            "你是机票助手。请基于给定的结构化数据生成 JSON，字段只允许包含 "
            "recommendation,signals,confidence。不要计算新数字。输入："
            f"{json.dumps(payload, ensure_ascii=False)}"
        )
        try:
            content = await self.chat_completion(
                messages=[
                    {"role": "system", "content": "你是一个严谨的机票搜索助手。"},
                    {"role": "user", "content": prompt},
                ]
            )
            parsed = json.loads(self._extract_json(content))
        except Exception:
            return None

        normalized = self._normalize_recommendation_payload(parsed)
        if not normalized["recommendation"]:
            return None
        return normalized

    def _parse_intent_heuristic(self, text: str) -> dict[str, Any]:
        origin = self._extract_origin(text) or self._default_origin
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

    def _generate_recommendation_heuristic(self, metrics: dict[str, Any]) -> dict[str, Any]:
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

        return {"recommendation": recommendation, "signals": signals, "confidence": confidence}

    def _extract_origin(self, text: str) -> str | None:
        match = re.search(r"(?:从|出发地)\s*([一-龥]{2,4})", text)
        if match:
            return CITY_TO_AIRPORT.get(match.group(1))
        return None

    def _extract_destination(self, text: str) -> str | None:
        for city_name, airport_code in LOCATION_ALIASES.items():
            if airport_code != self._default_origin and city_name in text:
                return airport_code

        match = re.search(r"(?:去|到)\s*([一-龥]{2,4})", text)
        if match:
            return self._normalize_location_code(match.group(1), "")
        for city_name, airport_code in CITY_TO_AIRPORT.items():
            if city_name in text and airport_code != self._default_origin:
                return airport_code
        return None

    def _extract_budget(self, text: str) -> int | None:
        for pattern in [
            r"(\d+)\s*(?:元)?(?:以内|以下|之内|内)",
            r"预算\s*(\d+)",
            r"不超过\s*(\d+)",
            r"低于\s*(\d+)",
        ]:
            match = re.search(pattern, text)
            if match:
                return int(match.group(1))
        return None

    def _extract_dates(self, text: str) -> tuple[str, str]:
        for keyword, date_range in HOLIDAY_RANGES.items():
            if keyword in text:
                year = self._today().year
                start = date(year, date_range[0][0], date_range[0][1]).isoformat()
                end = date(year, date_range[1][0], date_range[1][1]).isoformat()
                return start, end

        full_dates = re.findall(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", text)
        if full_dates:
            parsed = [date(int(y), int(m), int(d)).isoformat() for y, m, d in full_dates]
            return (parsed[0], parsed[0]) if len(parsed) == 1 else (parsed[0], parsed[1])

        partial = re.findall(r"(\d{1,2})月(\d{1,2})日", text)
        if partial:
            year = self._today().year
            parsed = [date(year, int(m), int(d)).isoformat() for m, d in partial]
            return (parsed[0], parsed[0]) if len(parsed) == 1 else (parsed[0], parsed[1])

        today = self._today().isoformat()
        return today, today

    def _build_normalized_text(self, parsed: dict[str, Any]) -> str:
        budget_text = "预算不限" if parsed.get("budget") is None else f"预算≤{parsed['budget']}"
        return (
            f"{parsed.get('origin', 'BJS')}->{parsed.get('destination', 'SYX')}, "
            f"{parsed.get('date_start', '')} 至 {parsed.get('date_end', '')}, {budget_text}"
        )

    def _normalize_intent_payload(self, parsed: dict[str, Any]) -> dict[str, Any]:
        today = self._today()
        origin = self._normalize_location_code(parsed.get("origin"), fallback=self._default_origin)
        destination = self._normalize_location_code(parsed.get("destination"), fallback="SYX")
        date_start = self._normalize_date_value(parsed.get("date_start"), fallback=today.isoformat())
        date_end = self._normalize_date_value(parsed.get("date_end"), fallback=date_start)
        budget = self._normalize_budget_value(parsed.get("budget"))
        return {
            "origin": origin,
            "destination": destination,
            "date_start": date_start,
            "date_end": date_end,
            "budget": budget,
        }

    def _normalize_recommendation_payload(self, parsed: dict[str, Any]) -> dict[str, Any]:
        recommendation = str(
            parsed.get("recommendation")
            or parsed.get("text")
            or parsed.get("verdict")
            or ""
        ).strip()
        raw_signals = parsed.get("signals")
        signals: list[str]
        if isinstance(raw_signals, list):
            signals = [str(item).strip() for item in raw_signals if str(item).strip()]
        elif isinstance(raw_signals, str):
            signals = [part.strip() for part in re.split(r"[，,；;\n]+", raw_signals) if part.strip()]
        else:
            signals = []

        confidence = self._normalize_confidence_value(parsed.get("confidence"))
        return {
            "recommendation": recommendation or "建议继续观察。",
            "signals": signals,
            "confidence": confidence,
        }

    def _merge_intent_with_heuristic(
        self,
        llm_result: dict[str, Any],
        heuristic: dict[str, Any],
    ) -> dict[str, Any]:
        result = dict(llm_result)

        if heuristic.get("origin") and (
            llm_result.get("origin") in (None, "", self._default_origin)
            or self._text_contains_explicit_origin(llm_result.get("origin"), heuristic.get("origin"))
        ):
            result["origin"] = heuristic["origin"]

        if heuristic.get("destination") and (
            llm_result.get("destination") in (None, "", "SYX")
            or not self._is_same_location(llm_result.get("destination"), heuristic.get("destination"))
        ):
            result["destination"] = heuristic["destination"]

        if heuristic.get("budget") is not None and llm_result.get("budget") is None:
            result["budget"] = heuristic["budget"]

        if heuristic.get("date_start") and self._should_prefer_heuristic_date(
            llm_result.get("date_start"),
            heuristic.get("date_start"),
        ):
            result["date_start"] = heuristic["date_start"]

        if heuristic.get("date_end") and self._should_prefer_heuristic_date(
            llm_result.get("date_end"),
            heuristic.get("date_end"),
        ):
            result["date_end"] = heuristic["date_end"]

        return result

    def _normalize_location_code(self, value: Any, fallback: str) -> str:
        if value is None:
            return fallback

        text = str(value).strip()
        if not text:
            return fallback

        city_match = CITY_TO_AIRPORT.get(text)
        if city_match:
            return city_match

        lowered = text.lower().replace(" ", "").replace("-", "").replace("_", "")
        alias_match = LOCATION_ALIASES.get(lowered) or LOCATION_ALIASES.get(text)
        if alias_match:
            return alias_match

        code = text.upper()
        if re.fullmatch(r"[A-Z]{3}", code):
            return code
        return fallback

    def _is_same_location(self, left: Any, right: Any) -> bool:
        if left in (None, "") or right in (None, ""):
            return False
        return self._normalize_location_code(left, "") == self._normalize_location_code(right, "")

    def _text_contains_explicit_origin(self, llm_origin: Any, heuristic_origin: Any) -> bool:
        return self._is_same_location(llm_origin, heuristic_origin)

    def _normalize_date_value(self, value: Any, fallback: str) -> str:
        if value in (None, ""):
            return fallback

        text = str(value).strip()
        if not text:
            return fallback

        normalized = text.replace("/", "-").replace(".", "-").replace("年", "-").replace("月", "-").replace("日", "")
        normalized = re.sub(r"\s+", "", normalized)

        for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(normalized, fmt).date().isoformat()
            except ValueError:
                continue

        partial_match = re.fullmatch(r"(\d{1,2})-(\d{1,2})", normalized)
        if partial_match:
            month = int(partial_match.group(1))
            day = int(partial_match.group(2))
            return date(self._today().year, month, day).isoformat()

        compact_match = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", normalized)
        if compact_match:
            return date(
                int(compact_match.group(1)),
                int(compact_match.group(2)),
                int(compact_match.group(3)),
            ).isoformat()

        return fallback

    @staticmethod
    def _normalize_budget_value(value: Any) -> int | None:
        if value in (None, ""):
            return None
        if isinstance(value, (int, float)):
            return int(value)

        match = re.search(r"\d+", str(value))
        return int(match.group(0)) if match else None

    @staticmethod
    def _normalize_confidence_value(value: Any) -> str:
        if value in (None, ""):
            return "medium"

        if isinstance(value, (int, float)):
            score = float(value)
        else:
            text = str(value).strip().lower()
            keyword_map = {
                "high": "high",
                "medium": "medium",
                "med": "medium",
                "low": "low",
                "高": "high",
                "中": "medium",
                "低": "low",
            }
            if text in keyword_map:
                return keyword_map[text]

            try:
                score = float(text)
            except ValueError:
                return "medium"

        if score >= 0.8:
            return "high"
        if score >= 0.4:
            return "medium"
        return "low"

    @staticmethod
    def _should_prefer_heuristic_date(llm_date: Any, heuristic_date: Any) -> bool:
        if heuristic_date in (None, ""):
            return False
        return llm_date in (None, "", heuristic_date)

    @staticmethod
    def _extract_json(content: str) -> str:
        match = re.search(r"\{.*\}", content, flags=re.S)
        return match.group(0) if match else content

    @staticmethod
    def _today() -> date:
        from datetime import timezone
        return datetime.now(tz=timezone.utc).date()


# 向后兼容：旧代码 import LLMClient 仍可用
class LLMClient(UnifiedLLMClient):
    def __init__(self, settings: Any) -> None:  # type: ignore[override]
        super().__init__(
            provider=settings.llm_provider,
            api_key=settings.llm_api_key,
            base_url=settings.llm_base_url,
            model=settings.llm_model,
            timeout=settings.request_timeout_seconds,
            default_origin=settings.default_origin,
        )
