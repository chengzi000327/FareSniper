"""Tiny async Redis stand-in for tests that don't need real Redis semantics.

Only the surface used by FareSniper's session_store / alert_checker is
modelled: `set`, `setex`, `get`, `delete`, `close`. Adding more methods
should happen on demand from the failing tests, not speculatively.
"""
from __future__ import annotations

import time
from typing import Optional


class FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, tuple[str, Optional[float]]] = {}

    async def set(self, key: str, value: str, ex: Optional[int] = None) -> None:
        expires_at = time.time() + ex if ex else None
        self._store[key] = (value, expires_at)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        await self.set(key, value, ex=ttl)

    async def get(self, key: str) -> Optional[str]:
        item = self._store.get(key)
        if item is None:
            return None
        value, expires_at = item
        if expires_at is not None and time.time() > expires_at:
            self._store.pop(key, None)
            return None
        return value

    async def delete(self, key: str) -> int:
        return 1 if self._store.pop(key, None) is not None else 0

    async def close(self) -> None:
        self._store.clear()
