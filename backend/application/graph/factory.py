"""SearchGraph factory."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

from backend.application.graph.state import WorkflowState


def build_search_graph():
    from backend.application.graph.nodes.bootstrap_session import bootstrap_session_context
    from backend.application.graph.nodes.clarify import clarify_response
    from backend.application.graph.nodes.fetch_flights import run_flight_search
    from backend.application.graph.nodes.judge_value import synthesize_decision
    from backend.application.graph.nodes.match_preferences import run_preference_match
    from backend.application.graph.nodes.parse_intent import (
        parse_user_intent,
        route_after_intent,
    )
    from backend.application.graph.nodes.render_response import render_response

    graph = StateGraph(WorkflowState)

    graph.add_node("bootstrap_session_context", bootstrap_session_context)
    graph.add_node("parse_user_intent", parse_user_intent)
    graph.add_node("clarify_response", clarify_response)
    graph.add_node("run_flight_search", run_flight_search)
    graph.add_node("run_preference_match", run_preference_match)
    graph.add_node("synthesize_decision", synthesize_decision)
    graph.add_node("render_response", render_response)

    graph.set_entry_point("bootstrap_session_context")
    graph.add_edge("bootstrap_session_context", "parse_user_intent")
    graph.add_conditional_edges(
        "parse_user_intent",
        route_after_intent,
        {"complete": "run_flight_search", "clarify": "clarify_response"},
    )
    graph.add_edge("clarify_response", END)
    graph.add_edge("run_flight_search", "run_preference_match")
    graph.add_edge("run_preference_match", "synthesize_decision")
    graph.add_edge("synthesize_decision", "render_response")
    graph.add_edge("render_response", END)

    return graph.compile()


class _LazySearchGraph:
    """Legacy DAG wrapper that avoids LLM initialization during module import."""

    _compiled = None

    def _get(self):
        if self._compiled is None:
            self._compiled = build_search_graph()
        return self._compiled

    async def ainvoke(self, *args, **kwargs):
        return await self._get().ainvoke(*args, **kwargs)

    def invoke(self, *args, **kwargs):
        return self._get().invoke(*args, **kwargs)

    def get_graph(self, *args, **kwargs):
        return self._get().get_graph(*args, **kwargs)


search_graph = _LazySearchGraph()


# ── Launch-plan ReAct factory (TG-05 · Task 4) ──────────────────────────────
# build_graph() returns a fresh compiled graph with a single placeholder
# node — TG-08 will replace the body with the ReAct agent + tool router +
# render_response wiring. get_graph() memoises one compiled instance for the
# FastAPI lifespan to consume; tests can call build_graph() directly to get
# an isolated copy that's safe to mutate.

_compiled_graph = None


def _route_after_react(state: dict) -> str:
    last = state["messages"][-1] if state.get("messages") else None
    if last and getattr(last, "tool_calls", None):
        return "tool_router"
    return "render_response"


def build_graph():
    """Compile the PRD slot-filling graph: bootstrap → fill slots → clarify/search → render."""
    from backend.application.graph.nodes.bootstrap_session import bootstrap_session
    from backend.application.graph.nodes.render_response import render_response
    from backend.application.graph.nodes.slot_filling import (
        fill_intent_slots,
        route_after_slot_filling,
        run_slot_search,
        dynamic_intent_response,
        slot_clarify_response,
    )

    sg = StateGraph(WorkflowState)
    sg.add_node("bootstrap_session", bootstrap_session)
    sg.add_node("fill_intent_slots", fill_intent_slots)
    sg.add_node("clarify_response", slot_clarify_response)
    sg.add_node("dynamic_intent_response", dynamic_intent_response)
    sg.add_node("run_slot_search", run_slot_search)
    sg.add_node("render_response", render_response)

    sg.set_entry_point("bootstrap_session")
    sg.add_edge("bootstrap_session", "fill_intent_slots")
    sg.add_conditional_edges(
        "fill_intent_slots",
        route_after_slot_filling,
        {
            "clarify_response": "clarify_response",
            "run_slot_search": "run_slot_search",
            "dynamic_intent_response": "dynamic_intent_response",
        },
    )
    sg.add_edge("clarify_response", END)
    sg.add_edge("dynamic_intent_response", END)
    sg.add_edge("run_slot_search", "render_response")
    sg.add_edge("render_response", END)

    return sg.compile()


def get_graph():
    """Return the singleton compiled graph used at runtime."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


def reset_graph_cache() -> None:
    """Test-only helper: drop the singleton so the next get_graph() rebuilds."""
    global _compiled_graph
    _compiled_graph = None
