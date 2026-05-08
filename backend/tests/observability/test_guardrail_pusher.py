import pytest
from backend.infrastructure.observability.guardrail_pusher import push_breach
from backend.analytics.guardrails import GuardrailReport


class _FakeLangfuse:
    def __init__(self):
        self.scores = []

    def score(self, *, name, value, **kwargs):
        self.scores.append({"name": name, "value": value})

    def flush(self):
        pass


@pytest.fixture
def captured_langfuse(monkeypatch):
    import backend.infrastructure.observability.guardrail_pusher as gp
    fake = _FakeLangfuse()
    monkeypatch.setattr(gp, "_get_langfuse", lambda: fake)
    return fake


@pytest.mark.asyncio
async def test_push_invokes_langfuse(monkeypatch, captured_langfuse):
    rep = GuardrailReport(
        deeplink_failure_rate=0.1,
        ai_misleading_rate=0.0,
        p95_latency_ms=2000,
        breached=["deeplink_failure"],
    )
    await push_breach(rep)
    assert captured_langfuse.scores[-1]["name"] == "deeplink_failure"
    assert captured_langfuse.scores[-1]["value"] == 0.1
