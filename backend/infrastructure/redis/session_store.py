from __future__ import annotations

import json
from dataclasses import asdict

import redis.asyncio as redis

from backend.application.contracts.intent import SlotBundle
from backend.config import settings

_pool: redis.Redis | None = None
TTL = 1800  # 30 min


def _redis() -> redis.Redis:
    if _pool is None:
        raise RuntimeError("redis not initialized; call init_redis() first")
    return _pool


async def init_redis() -> None:
    global _pool
    _pool = redis.from_url(settings.redis_url, decode_responses=True)


async def close_redis() -> None:
    global _pool
    if _pool:
        await _pool.aclose()
        _pool = None


async def save_slots(session_id: str, slots: SlotBundle) -> None:
    await _redis().setex(f"sess:{session_id}", TTL, json.dumps(asdict(slots)))


async def load_slots(session_id: str) -> SlotBundle | None:
    raw = await _redis().get(f"sess:{session_id}")
    if not raw:
        return None
    return SlotBundle(**json.loads(raw))
