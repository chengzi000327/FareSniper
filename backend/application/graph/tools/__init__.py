"""Tool registry for the ReAct graph.

Lazy-imports each tool module so that missing implementations during TG-09
don't crash the whole graph — absent tools are silently skipped.
"""
from __future__ import annotations

import importlib

_TOOL_MODULES = [
    ("backend.application.graph.tools.ask_user", "ask_user"),
    ("backend.application.graph.tools.search_flights", "search_flights"),
    ("backend.application.graph.tools.get_preferences", "get_preferences"),
    ("backend.application.graph.tools.match_preferences", "match_preferences"),
    ("backend.application.graph.tools.judge_value", "judge_value"),
    ("backend.application.graph.tools.set_alert", "set_alert"),
    ("backend.application.graph.tools.fallback_form", "fallback_form"),
]


def load_available_tools() -> list:
    tools: list = []
    for mod_path, name in _TOOL_MODULES:
        try:
            mod = importlib.import_module(mod_path)
            tools.append(getattr(mod, name))
        except (ModuleNotFoundError, AttributeError):
            continue
    return tools
