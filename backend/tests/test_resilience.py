"""
Step 9 容错机制测试
"""
from __future__ import annotations

import asyncio

import pytest

from backend.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitOpenError,
    CircuitState,
)
from backend.resilience.retry import retry_with_backoff


# ── CircuitBreaker ────────────────────────────────────────────────────────────

async def test_circuit_breaker_starts_closed():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1)
    assert cb.state == CircuitState.CLOSED


async def test_circuit_breaker_opens_after_threshold():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1)

    async def always_fail():
        raise RuntimeError("boom")

    for _ in range(3):
        with pytest.raises(RuntimeError):
            await cb.call(always_fail)

    assert cb.state == CircuitState.OPEN


async def test_circuit_breaker_raises_when_open():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=60)

    async def always_fail():
        raise RuntimeError("boom")

    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.call(always_fail)

    # Should raise CircuitOpenError, not RuntimeError
    from backend.resilience.circuit_breaker import CircuitOpenError
    with pytest.raises(CircuitOpenError):
        await cb.call(always_fail)


async def test_circuit_breaker_half_open_after_recovery():
    cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)

    async def always_fail():
        raise RuntimeError("boom")

    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.call(always_fail)

    assert cb.state == CircuitState.OPEN
    await asyncio.sleep(0.2)

    # After timeout, next call enters HALF_OPEN
    call_count = 0

    async def succeed():
        nonlocal call_count
        call_count += 1
        return "ok"

    result = await cb.call(succeed)
    assert result == "ok"
    assert cb.state == CircuitState.CLOSED


async def test_circuit_breaker_success_resets_failures():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1)

    async def always_fail():
        raise RuntimeError("boom")

    async def succeed():
        return "ok"

    # 2 failures
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.call(always_fail)

    # 1 success → failure counter resets
    result = await cb.call(succeed)
    assert result == "ok"
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0


async def test_circuit_breaker_closed_calls_can_overlap():
    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=1)
    both_started = asyncio.Event()
    started = 0

    async def rendezvous(value):
        nonlocal started
        started += 1
        if started == 2:
            both_started.set()
        await asyncio.wait_for(both_started.wait(), timeout=0.1)
        return value

    left, right = await asyncio.gather(
        cb.call(rendezvous, "left"),
        cb.call(rendezvous, "right"),
    )

    assert (left, right) == ("left", "right")


async def test_circuit_breaker_allows_only_one_half_open_probe():
    cb = CircuitBreaker(failure_threshold=1, recovery_timeout=0.01)

    async def fail():
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await cb.call(fail)
    await asyncio.sleep(0.02)

    probe_started = asyncio.Event()
    release_probe = asyncio.Event()

    async def probe():
        probe_started.set()
        await release_probe.wait()
        return "recovered"

    first = asyncio.create_task(cb.call(probe))
    await probe_started.wait()

    with pytest.raises(CircuitOpenError):
        await asyncio.wait_for(cb.call(probe), timeout=0.05)

    release_probe.set()
    assert await first == "recovered"
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0


# ── retry_with_backoff ────────────────────────────────────────────────────────

async def test_retry_succeeds_on_first_attempt():
    call_count = 0

    async def succeed():
        nonlocal call_count
        call_count += 1
        return "ok"

    result = await retry_with_backoff(succeed, max_retries=3, base_delay=0.01)
    assert result == "ok"
    assert call_count == 1


async def test_retry_succeeds_on_second_attempt():
    call_count = 0

    async def fail_once():
        nonlocal call_count
        call_count += 1
        if call_count < 2:
            raise RuntimeError("transient")
        return "recovered"

    result = await retry_with_backoff(fail_once, max_retries=3, base_delay=0.01)
    assert result == "recovered"
    assert call_count == 2


async def test_retry_raises_after_max_retries():
    call_count = 0

    async def always_fail():
        nonlocal call_count
        call_count += 1
        raise RuntimeError("permanent")

    with pytest.raises(RuntimeError, match="permanent"):
        await retry_with_backoff(always_fail, max_retries=3, base_delay=0.01)

    assert call_count == 4  # 1 initial + 3 retries


async def test_retry_exponential_backoff():
    """验证重试间隔在增长（简单通过计时确认量级）。"""
    import time

    call_count = 0
    timestamps = []

    async def record_and_fail():
        nonlocal call_count
        call_count += 1
        timestamps.append(time.monotonic())
        raise RuntimeError("boom")

    with pytest.raises(RuntimeError):
        await retry_with_backoff(
            record_and_fail,
            max_retries=2,
            base_delay=0.05,
            jitter=False,
        )

    assert len(timestamps) == 3
    gap1 = timestamps[1] - timestamps[0]
    gap2 = timestamps[2] - timestamps[1]
    # 第二次间隔应大于第一次（指数退避）
    assert gap2 >= gap1 * 1.5
