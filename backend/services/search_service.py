"""搜索主链路：IntentParser → PreferenceMatch → ValueJudge（PRD 5/6/7）。"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

from backend.data_sources.mock_flights import CODE_CITY, get_mock_flights
from backend.services.holiday import is_holiday
from backend.services.intent_parser import IntentParser, is_intent_complete
from backend.services.memory_learner import learn_from_query_history, learn_from_search
from backend.services.preference_matcher import run_preference_match
from backend.services.recommend_scorer import sort_deals
from backend.services.value_judge import ValueJudge


def _now() -> str:
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_CLARIFY_PROMPTS = {
    "origin": "请问您从哪个城市出发？",
    "destination": "请问目的地是哪里？",
    "date_start": "请问什么时间出发？",
}

_EMPTY_ANALYSIS = {
    "match_score": 0.0,
    "within_budget": False,
    "matched_preferences": [],
}


class SearchService:
    def __init__(
        self,
        llm_client=None,
        data_source_registry=None,
        session_factory=None,
        redis_client=None,
        model_intent: str = "qwen-turbo",
        model_judge: str = "qwen-plus",
        # 向后兼容旧参数
        intention_agent=None,
        orchestration_agent=None,
        memory_service=None,
    ) -> None:
        self.llm_client = llm_client
        self.data_source_registry = data_source_registry
        self.session_factory = session_factory
        self.redis_client = redis_client
        self.intent_parser = IntentParser(llm_client=llm_client, model=model_intent)
        self.value_judge = ValueJudge(llm_client=llm_client, model=model_judge)

    async def search(
        self,
        user_id: str,
        message: str,
        session_id: str | None = None,
    ) -> dict[str, Any]:
        # ── 1. 加载 session 历史 ────────────────────────────────────────────
        session_history = await self._load_session_history(session_id)

        # ── 2. IntentParser：解析意图 ───────────────────────────────────────
        intent = await self.intent_parser.parse(message, session_history)

        if intent.get("_parse_failed"):
            return self._fallback_response(user_id, "没听明白，换个说法试试？", fallback=True)

        # ── 3. 意图完整性检查 ───────────────────────────────────────────────
        if not is_intent_complete(intent):
            clarify_text = _build_clarify_text(intent)
            clarify_count = await self._get_clarify_count(session_id) + 1

            # 超过 2 次追问 → 降级提示结构化表单
            if clarify_count >= 2:
                return self._fallback_response(
                    user_id,
                    "填一下这几项吧",
                    clarify_count=clarify_count,
                    fallback=False,
                )

            await self._save_clarify_count(session_id, clarify_count)
            return self._clarify_response(user_id, clarify_text, clarify_count)

        # ── 4. 并行：查价 + 读偏好 ─────────────────────────────────────────
        flights_task = asyncio.create_task(
            self._fetch_flights(intent)
        )
        prefs_task = asyncio.create_task(
            self._get_preferences(user_id)
        )
        flights, user_memory = await asyncio.gather(flights_task, prefs_task)

        if not flights:
            return self._fallback_response(user_id, "暂未找到航班，试试换个日期", fallback=True)

        # ── 5. PreferenceMatch（纯工程） ────────────────────────────────────
        pref_results = run_preference_match(flights, user_memory)

        # ── 6. is_holiday + recommend_score + 排序 ─────────────────────────
        is_holiday_map = {
            f.get("depart_date", ""): is_holiday(f.get("depart_date", ""))
            for f in flights
        }
        flights = sort_deals(flights, pref_results)

        # ── 7. ValueJudge（LLM 或启发式） ──────────────────────────────────
        judge_results = await self.value_judge.judge(flights, pref_results, is_holiday_map)
        judge_map = {j.get("flight_no", ""): j for j in judge_results}

        # 将 signals + verdict 写入每个 flight
        for f in flights:
            key = f.get("flight_no", f.get("id", ""))
            jud = judge_map.get(key, {})
            f["signals"] = jud.get("signals", [])
            f["verdict"] = jud.get("advice", "价格正常，可继续关注")

        # ── 8. 组装响应 ─────────────────────────────────────────────────────
        best = flights[0] if flights else {}
        top_signals = best.get("signals", [])
        within_budget = any("心理价位" in r for r in top_signals)
        has_hist_low = "历史低价" in top_signals

        action: str
        if has_hist_low and within_budget:
            action = "buy_now"
            confidence = "high"
        elif has_hist_low or within_budget:
            action = "watch"
            confidence = "medium"
        else:
            action = "watch"
            confidence = "low"

        pref_reasons: list[str] = []
        for p in pref_results:
            pref_reasons.extend(p.get("reasons", []))

        # 计算 analysis 字段
        prices = [f.get("price", 0) for f in flights]
        avg_90d_vals = [f.get("history_avg_90d") for f in flights if f.get("history_avg_90d")]
        best_price = best.get("price", 0)
        best_avg = best.get("history_avg_90d")
        lower_than_avg = round((best_avg - best_price) / best_avg, 4) if best_avg and best_price else None

        origin_city = intent.get("origin") or CODE_CITY.get(intent.get("origin_code", ""), "")
        dest_city = intent.get("destination") or CODE_CITY.get(intent.get("destination_code", ""), "")

        result = {
            "user_id": user_id,
            "query": {
                "raw_text": intent.get("raw_text", message),
                "normalized_text": intent.get("normalized_text", message),
                "origin_city": origin_city,
                "origin_code": intent.get("origin_code", ""),
                "destination_city": dest_city,
                "destination_code": intent.get("destination_code", ""),
                "date_start": intent.get("date_start", ""),
                "date_end": intent.get("date_end", intent.get("date_start", "")),
                "budget": intent.get("budget"),
            },
            "deals": flights,
            "analysis": {
                "min_price": min(prices) if prices else None,
                "max_price": max(prices) if prices else None,
                "avg_price": int(sum(prices) / len(prices)) if prices else None,
                "avg_90d": int(sum(avg_90d_vals) / len(avg_90d_vals)) if avg_90d_vals else None,
                "lower_than_avg": lower_than_avg,
                "price_spread_pct": None,
                "match_score": round(len([p for p in pref_results if p.get("matched")]) / max(len(pref_results), 1), 2),
                "within_budget": within_budget,
                "matched_preferences": list(set(pref_reasons)),
            },
            "recommendation": {
                "action": action,
                "text": best.get("verdict", "价格正常，可继续关注"),
                "confidence": confidence,
                "signals": top_signals,
            },
            "meta": {
                "generated_at": _now(),
                "source": "mock",
                "request_id": str(uuid.uuid4()),
                "result_count": len(flights),
                "fallback_mode": False,
            },
        }

        # ── 9. 异步记忆更新（不阻塞） ────────────────────────────────────
        asyncio.create_task(learn_from_search(user_id, intent, self.session_factory))
        asyncio.create_task(learn_from_query_history(user_id, self.session_factory))

        return result

    # ── internal helpers ────────────────────────────────────────────────────

    async def _fetch_flights(self, intent: dict[str, Any]) -> list[dict[str, Any]]:
        origin = intent.get("origin") or intent.get("origin_code", "")
        dest = intent.get("destination") or intent.get("destination_code", "")
        date_start = intent.get("date_start", "")

        try:
            flights = get_mock_flights(origin, dest, date_start)
        except Exception:
            flights = []

        # 真实数据源兜底（MVP 不接入）
        if not flights and self.data_source_registry:
            try:
                source = self.data_source_registry.get("ctrip")
                if source:
                    flights = await source.search_flights(
                        origin=intent.get("origin_code", "BJS"),
                        destination=intent.get("destination_code", "SYX"),
                        date_start=date_start,
                        date_end=intent.get("date_end", date_start),
                    )
            except Exception:
                pass

        # direct_only 过滤
        if "direct_only" in (intent.get("constraints") or []):
            flights = [f for f in flights if f.get("stops", 0) == 0]

        return flights

    async def _get_preferences(self, user_id: str) -> dict[str, Any]:
        if self.session_factory:
            try:
                async with self.session_factory() as db:
                    from backend.memory.long_term import LongTermMemory
                    ltm = LongTermMemory(db)
                    prefs = await ltm.get_preferences(user_id)
                    return prefs or {}
            except Exception:
                pass
        return {}

    async def _load_session_history(self, session_id: str | None) -> list[dict[str, str]]:
        if not session_id or not self.session_factory:
            return []
        try:
            from sqlalchemy import select
            from backend.db.models import ChatHistory
            async with self.session_factory() as db:
                stmt = (
                    select(ChatHistory)
                    .where(ChatHistory.session_id == session_id)
                    .order_by(ChatHistory.created_at.asc())
                    .limit(10)
                )
                rows = (await db.execute(stmt)).scalars().all()
                return [{"role": r.role, "content": r.content} for r in rows]
        except Exception:
            return []

    async def _get_clarify_count(self, session_id: str | None) -> int:
        if not session_id or not self.redis_client:
            return 0
        try:
            val = await self.redis_client.get(f"clarify:{session_id}")
            return int(val) if val else 0
        except Exception:
            return 0

    async def _save_clarify_count(self, session_id: str | None, count: int) -> None:
        if not session_id or not self.redis_client:
            return
        try:
            await self.redis_client.setex(f"clarify:{session_id}", 1800, count)
        except Exception:
            pass

    def _clarify_response(self, user_id: str, text: str, clarify_count: int) -> dict[str, Any]:
        return {
            "user_id": user_id,
            "query": None,
            "deals": [],
            "analysis": _EMPTY_ANALYSIS,
            "recommendation": {
                "action": "watch",
                "text": text,
                "confidence": "low",
                "signals": [],
            },
            "meta": {
                "generated_at": _now(),
                "fallback_mode": False,
                "clarify_count": clarify_count,
            },
        }

    def _fallback_response(
        self,
        user_id: str,
        text: str,
        fallback: bool = True,
        clarify_count: int | None = None,
    ) -> dict[str, Any]:
        meta: dict[str, Any] = {"generated_at": _now(), "fallback_mode": fallback}
        if clarify_count is not None:
            meta["clarify_count"] = clarify_count
        return {
            "user_id": user_id,
            "query": None,
            "deals": [],
            "analysis": _EMPTY_ANALYSIS,
            "recommendation": {
                "action": "skip",
                "text": text,
                "confidence": "low",
                "signals": [],
            },
            "meta": meta,
        }


def _build_clarify_text(intent: dict[str, Any]) -> str:
    if not intent.get("origin"):
        return _CLARIFY_PROMPTS["origin"]
    if not intent.get("destination"):
        return _CLARIFY_PROMPTS["destination"]
    return _CLARIFY_PROMPTS["date_start"]
