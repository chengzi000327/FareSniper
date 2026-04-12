from __future__ import annotations

import json
from typing import Any

KEY_PREFIX = "faresniper:chat:"
WINDOW_SIZE = 10
TTL_SECONDS = 3600


class ShortTermMemory:
    """Redis 滑动窗口，每个 user_id 保留最近 WINDOW_SIZE 条消息，TTL 1小时。"""

    def __init__(self, redis_client: Any) -> None:
        self._r = redis_client

    def _key(self, user_id: str) -> str:
        return f"{KEY_PREFIX}{user_id}"

    async def push(self, user_id: str, message: dict[str, Any]) -> None:
        key = self._key(user_id)
        await self._r.rpush(key, json.dumps(message, ensure_ascii=False))
        await self._r.ltrim(key, -WINDOW_SIZE, -1)
        await self._r.expire(key, TTL_SECONDS)

    async def get(self, user_id: str) -> list[dict[str, Any]]:
        key = self._key(user_id)
        raw = await self._r.lrange(key, 0, -1)
        return [json.loads(item) for item in raw]

    async def clear(self, user_id: str) -> None:
        await self._r.delete(self._key(user_id))
