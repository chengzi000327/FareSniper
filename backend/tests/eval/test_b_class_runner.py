import pytest
from backend.eval.runners.b_class import run_b_class


@pytest.fixture
def stub_graph_high_accuracy(monkeypatch):
    """Stub get_graph() to return a fake graph that always succeeds."""
    from backend.application.contracts.decision import FrontendResponse

    class _FakeGraph:
        async def ainvoke(self, state):
            return {
                "response": FrontendResponse(
                    deals=[],
                    recommendation={"text": "找到特价机票，推荐搭乘"},
                    fallback=None,
                )
            }

    import backend.application.graph.factory as factory
    monkeypatch.setattr(factory, "get_graph", lambda: _FakeGraph())


@pytest.mark.asyncio
async def test_returns_5_dimensions(stub_graph_high_accuracy):
    report = await run_b_class(sample=5)
    assert {"intent_acc", "clarify_acc", "signal_acc", "advice_relevance", "format_compliance"} <= set(report.scores)
    for v in report.scores.values():
        assert 0.0 <= v <= 1.0
