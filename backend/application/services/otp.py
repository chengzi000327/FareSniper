from __future__ import annotations

import random

from backend.infrastructure.redis import session_store


def _redis():
    if session_store._pool is None:
        raise RuntimeError("redis not initialized; call init_redis() first")
    return session_store._pool


async def issue_code(phone: str) -> str:
    code = f"{random.randint(0, 999999):06d}"
    await _redis().setex(f"otp:{phone}", 300, code)
    return code


async def verify_code(phone: str, code: str) -> bool:
    raw = await _redis().get(f"otp:{phone}")
    return raw == code
