from langfuse import Langfuse
from backend.analytics.guardrails import GuardrailReport

_FIELD_MAP = {
    "deeplink_failure": "deeplink_failure_rate",
    "ai_misleading": "ai_misleading_rate",
    "p95_latency": "p95_latency_ms",
}


def _get_langfuse() -> Langfuse:
    return Langfuse()


async def push_breach(rep: GuardrailReport) -> None:
    if not rep.breached:
        return
    lf = _get_langfuse()
    for name in rep.breached:
        field = _FIELD_MAP.get(name, name)
        value = getattr(rep, field, 0.0)
        lf.score(name=name, value=value)
