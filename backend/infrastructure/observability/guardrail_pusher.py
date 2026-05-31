from __future__ import annotations

import logging

from backend.analytics.guardrails import GuardrailReport

logger = logging.getLogger("faresniper.guardrail")

_FIELD_MAP = {
    "deeplink_failure": "deeplink_failure_rate",
    "ai_misleading": "ai_misleading_rate",
    "p95_latency": "p95_latency_ms",
}


async def push_breach(rep: GuardrailReport) -> None:
    if not rep.breached:
        return
    for name in rep.breached:
        field = _FIELD_MAP.get(name, name)
        value = getattr(rep, field, 0.0)
        logger.warning("guardrail_breach name=%s value=%s", name, value)
