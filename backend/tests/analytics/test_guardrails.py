from __future__ import annotations

import pytest

from backend.analytics.guardrails import (
    GuardrailReport,
    THRESHOLDS,
    classify_breaches,
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
