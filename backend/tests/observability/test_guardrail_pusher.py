import logging

import pytest
from backend.infrastructure.observability.guardrail_pusher import push_breach
from backend.analytics.guardrails import GuardrailReport


@pytest.mark.asyncio
async def test_push_logs_breach(caplog):
    rep = GuardrailReport(
        deeplink_failure_rate=0.1,
        ai_misleading_rate=0.0,
        p95_latency_ms=2000,
        breached=["deeplink_failure"],
    )
    with caplog.at_level(logging.WARNING, logger="faresniper.guardrail"):
        await push_breach(rep)
    assert any("deeplink_failure" in m for m in caplog.messages)
    assert any("0.1" in m for m in caplog.messages)


@pytest.mark.asyncio
async def test_push_no_breach_is_silent(caplog):
    rep = GuardrailReport(
        deeplink_failure_rate=0.0,
        ai_misleading_rate=0.0,
        p95_latency_ms=500,
        breached=[],
    )
    with caplog.at_level(logging.WARNING, logger="faresniper.guardrail"):
        await push_breach(rep)
    assert not caplog.messages
