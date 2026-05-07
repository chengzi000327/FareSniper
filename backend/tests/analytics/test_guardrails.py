from __future__ import annotations

import pytest

from backend.analytics.guardrails import (
    GuardrailReport,
    THRESHOLDS,
    classify_breaches,
    compute_guardrails,
)


def test_thresholds_match_prd_3_2():
    assert THRESHOLDS["deeplink_failure"] == 0.05
    assert THRESHOLDS["ai_misleading"] == 0.03
    assert THRESHOLDS["p95_latency"] == 3000


def test_no_breaches_when_under_thresholds():
    rep = GuardrailReport(
        deeplink_failure_rate=0.04,
        ai_misleading_rate=0.02,
        p95_latency_ms=2500.0,
    )
    classify_breaches(rep)
    assert rep.breached == []


@pytest.mark.parametrize(
    "metric,value,expected",
    [
        ("deeplink_failure_rate", 0.06, "deeplink_failure"),
        ("ai_misleading_rate", 0.04, "ai_misleading"),
        ("p95_latency_ms", 3500.0, "p95_latency"),
    ],
)
def test_breach_recorded_when_metric_over_threshold(metric, value, expected):
    rep = GuardrailReport()
    setattr(rep, metric, value)
    classify_breaches(rep)
    assert expected in rep.breached


def test_multiple_breaches_recorded_in_stable_order():
    rep = GuardrailReport(
        deeplink_failure_rate=0.10,
        ai_misleading_rate=0.05,
        p95_latency_ms=5000.0,
    )
    classify_breaches(rep)
    assert rep.breached == ["deeplink_failure", "ai_misleading", "p95_latency"]


@pytest.mark.asyncio
async def test_alarm_when_deeplink_failure_above_5pct(seeded_pg_with_events):
    rep = await compute_guardrails(window_minutes=60)
    # 16/20 events have deeplink_ok='false' → 0.80 ≫ 0.05 threshold
    assert rep.deeplink_failure_rate >= 0.05
    assert "deeplink_failure" in rep.breached
    # 1/20 events flagged as misleading → 0.05 > 0.03 threshold
    assert rep.ai_misleading_rate > 0
    assert "ai_misleading" in rep.breached
    # latency ramps from 1500 to 2450ms; p95 stays under the 3000 ceiling
    assert rep.p95_latency_ms < 3000
    assert "p95_latency" not in rep.breached


@pytest.mark.asyncio
async def test_no_alarm_when_no_events(seeded_pg):
    rep = await compute_guardrails(window_minutes=60)
    assert rep.deeplink_failure_rate == 0.0
    assert rep.breached == []
