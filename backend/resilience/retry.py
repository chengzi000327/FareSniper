from __future__ import annotations

import asyncio
import random
from typing import Any, Awaitable, Callable, Type, Tuple, TypeVar

T = TypeVar("T")


async def retry_with_backoff(
    fn: Callable[..., Awaitable[T]],
    *args: Any,
    max_retries: int = 3,
    base_delay: float = 0.5,
    max_delay: float = 30.0,
    jitter: bool = True,
    retryable_exceptions: Tuple[Type[BaseException], ...] = (Exception,),
    **kwargs: Any,
) -> T:
    """
    带指数退避的异步重试。

    Parameters
    ----------
    fn : async callable
        被重试的异步函数。
    max_retries : int
        最多重试次数（不含第一次调用）。
    base_delay : float
        基础等待时间（秒），每次翻倍。
    max_delay : float
        单次等待上限（秒）。
    jitter : bool
        是否在延迟上加随机抖动，避免惊群效应。
    retryable_exceptions : tuple
        只重试这些异常类型；其他异常直接抛出。
    """
    last_exc: BaseException | None = None
    delay = base_delay

    for attempt in range(max_retries + 1):
        try:
            return await fn(*args, **kwargs)
        except retryable_exceptions as exc:
            last_exc = exc
            if attempt == max_retries:
                break
            wait = min(delay, max_delay)
            if jitter:
                wait = wait * (0.5 + random.random())
            await asyncio.sleep(wait)
            delay *= 2

    assert last_exc is not None
    raise last_exc
