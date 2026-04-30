"""SearchGraph factory."""

from __future__ import annotations

from langgraph.graph import END, StateGraph

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
from backend.application.graph.state import WorkflowState


def build_search_graph():
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


search_graph = build_search_graph()
