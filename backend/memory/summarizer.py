from __future__ import annotations

from typing import Any

SUMMARY_CACHE_TTL = 1800  # 30 分钟

FIELD_LABELS = {
    "price_anchor": "心理价位",
    "preferred_origins": "常用出发地",
    "preferred_destinations": "想去的地方",
    "frequent_destinations": "常去目的地",
    "travel_window": "出行时间偏好",
    "cabin_preference": "舱位偏好",
}


class MemorySummarizer:
    """
    将长期记忆（偏好 + 历史）转换为自然语言摘要。
    优先读 Redis 缓存，缓存 miss 时用 LLM 或规则生成。
    """

    def __init__(self, redis_client: Any, llm_client: Any | None = None) -> None:
        self._r = redis_client
        self._llm = llm_client

    async def summarize(
        self,
        user_id: str,
        preferences: dict[str, Any] | None,
        recent_queries: list[dict[str, Any]],
    ) -> str:
        cache_key = f"faresniper:summary:{user_id}"
        cached = await self._r.get(cache_key)
        if cached:
            return cached

        summary = await self._generate(preferences, recent_queries)
        await self._r.set(cache_key, summary, ex=SUMMARY_CACHE_TTL)
        return summary

    async def _generate(
        self,
        preferences: dict[str, Any] | None,
        recent_queries: list[dict[str, Any]],
    ) -> str:
        if self._llm and getattr(self._llm, "_provider", "mock") != "mock":
            return await self._llm_summary(preferences, recent_queries)
        return self._rule_summary(preferences, recent_queries)

    async def _llm_summary(
        self,
        preferences: dict[str, Any] | None,
        recent_queries: list[dict[str, Any]],
    ) -> str:
        pref_text = self._rule_summary(preferences, recent_queries)
        try:
            return await self._llm.chat_completion(
                messages=[
                    {"role": "system", "content": "你是机票助手，用一句话总结用户的出行偏好。"},
                    {"role": "user", "content": pref_text},
                ],
                temperature=0.1,
            )
        except Exception:
            return pref_text

    def _rule_summary(
        self,
        preferences: dict[str, Any] | None,
        recent_queries: list[dict[str, Any]],
    ) -> str:
        parts: list[str] = []
        if preferences:
            for field, label in FIELD_LABELS.items():
                val = preferences.get(field)
                if val:
                    if isinstance(val, list):
                        parts.append(f"{label}：{'、'.join(val)}")
                    else:
                        parts.append(f"{label}：{val}")
        if recent_queries:
            texts = [q["query_text"] for q in recent_queries[:3]]
            parts.append(f"近期搜索：{'、'.join(texts)}")
        return "；".join(parts) if parts else "暂无记忆数据。"
