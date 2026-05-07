from __future__ import annotations

from backend.application.graph.factory import build_graph, get_graph


def test_build_graph_returns_compiled_runnable():
    g = build_graph()
    # Compiled LangGraph exposes invoke / ainvoke.
    assert hasattr(g, "invoke") or hasattr(g, "ainvoke")


def test_get_graph_is_singleton():
    g1 = get_graph()
    g2 = get_graph()
    assert g1 is g2


def test_build_graph_each_call_is_fresh():
    """build_graph() compiles a new graph; only get_graph() memoises."""
    a = build_graph()
    b = build_graph()
    assert a is not b
