from __future__ import annotations

import asyncio
import time
from enum import Enum
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "closed"      # 正常，允许请求通过
    OPEN = "open"          # 熔断，拒绝请求
    HALF_OPEN = "half_open"  # 试探，允许一次请求


class CircuitOpenError(RuntimeError):
    """电路处于 OPEN 状态时抛出。"""


class CircuitBreaker:
    """
    三态熔断器。

    Parameters
    ----------
    failure_threshold : int
        连续失败多少次后打开熔断（进入 OPEN）。
    recovery_timeout : float
        OPEN 状态持续多少秒后切换到 HALF_OPEN，允许一次试探。
    """

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0) -> None:
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count: int = 0
        self.last_failure_time: float = 0.0
        self._state: CircuitState = CircuitState.CLOSED
        self._lock = asyncio.Lock()
        self._half_open_in_flight = False

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN:
            if time.monotonic() - self.last_failure_time >= self.recovery_timeout:
                return CircuitState.HALF_OPEN
        return self._state

    async def call(
        self,
        fn: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        is_half_open_probe = False
        async with self._lock:
            current = self.state

            if current == CircuitState.OPEN:
                raise CircuitOpenError("Circuit is OPEN — request rejected")

            if current == CircuitState.HALF_OPEN:
                if self._half_open_in_flight:
                    raise CircuitOpenError("Circuit is HALF_OPEN — probe in flight")
                self._state = CircuitState.HALF_OPEN
                self._half_open_in_flight = True
                is_half_open_probe = True

        try:
            result = await fn(*args, **kwargs)
        except asyncio.CancelledError:
            if is_half_open_probe:
                async with self._lock:
                    self._state = CircuitState.OPEN
                    self.last_failure_time = time.monotonic()
                    self._half_open_in_flight = False
            raise
        except Exception:
            async with self._lock:
                if is_half_open_probe:
                    self._state = CircuitState.OPEN
                    self.last_failure_time = time.monotonic()
                    self._half_open_in_flight = False
                elif self._state == CircuitState.CLOSED:
                    self.failure_count += 1
                    if self.failure_count >= self.failure_threshold:
                        self._state = CircuitState.OPEN
                        self.last_failure_time = time.monotonic()
            raise
        else:
            async with self._lock:
                if is_half_open_probe:
                    self._reset()
                elif self._state == CircuitState.CLOSED:
                    self.failure_count = 0
            return result

    def _reset(self) -> None:
        self._state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0.0
        self._half_open_in_flight = False
