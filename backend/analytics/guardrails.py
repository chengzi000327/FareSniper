"""Guardrail metrics: deeplink failure, AI misleading, P95 latency.

Thresholds align with PRD §3.2. The DB aggregation uses PostgreSQL-only
operators (``FILTER``, ``percentile_cont``), which is fine for the
production path (live Railway PG) but cannot be exercised on the
SQLite ``seeded_pg`` fixture. Tests pin the threshold contract via the
pure ``classify_breaches`` function — populating ``GuardrailReport``
from real telemetry is verified against the live database in TG-15
once the per-event-type seeding fixtures land.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import text

from backend.infrastructure.db.base import get_session


THRESHOLDS = {
    "deeplink_failure": 0.05,
    "ai_misleading": 0.03,
    "p95_latency": 3000,
}


@dataclass
class GuardrailReport:
    deeplink_failure_rate: float = 0.0
    ai_misleading_rate: float = 0.0
    p95_latency_ms: float = 0.0
    breached: list[str] = field(default_factory=list)


def classify_breaches(report: GuardrailReport) -> None:
    """Append breach names to ``report.breached`` in canonical order."""
    if report.deeplink_failure_rate > THRESHOLDS["deeplink_failure"]:
        report.breached.append("deeplink_failure")
    if report.ai_misleading_rate > THRESHOLDS["ai_misleading"]:
        report.breached.append("ai_misleading")
    if report.p95_latency_ms > THRESHOLDS["p95_latency"]:
        report.breached.append("p95_latency")


_AGGREGATE_SQL = text(
    """
    SELECT
        COALESCE(AVG(CASE WHEN payload->>'deeplink_ok' = 'false' THEN 1 ELSE 0 END), 0) AS dl,
        COALESCE(AVG(CASE WHEN payload->>'misleading' = 'true' THEN 1 ELSE 0 END), 0) AS mis,
        COALESCE(
            percentile_cont(0.95) WITHIN GROUP (ORDER BY (payload->>'latency_ms')::int),
            0
        ) AS p95
    FROM analytics_events
    WHERE created_at > now() - (:m || ' minutes')::interval
    """
)


async def compute_guardrails(window_minutes: int = 60) -> GuardrailReport:
    async with get_session() as session:
        row = (await session.execute(_AGGREGATE_SQL, {"m": window_minutes})).one()
    report = GuardrailReport(
        deeplink_failure_rate=float(row.dl),
        ai_misleading_rate=float(row.mis),
        p95_latency_ms=float(row.p95),
    )
    classify_breaches(report)
    return report
