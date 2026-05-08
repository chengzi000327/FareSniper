from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable


async def with_retry(
    fn: Callable[[], Awaitable[Any]],
    *,
    attempts: int = 3,
    base_delay: float = 0.5,
) -> Any:
    last: Exception | None = None
    for i in range(attempts):
        try:
            return await fn()
        except Exception as e:
            last = e
            await asyncio.sleep(base_delay * (2**i))
    raise last  # type: ignore[misc]
