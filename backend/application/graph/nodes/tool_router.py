from __future__ import annotations

import json
import logging

from langchain_core.messages import ToolMessage

from backend.application.graph.tools import load_available_tools
from backend.application.services.search_events import safe_model_payload

INJECT_USER_ID_TOOLS = {"set_alert", "get_preferences"}
logger = logging.getLogger("faresniper.graph.tool_router")


async def tool_router(state: dict) -> dict:
    """Execute all tool calls in the last AI message and populate state fields."""
    tools_by_name = {t.name: t for t in load_available_tools()}
    last = state["messages"][-1]
    out_msgs: list = []
    clarify_inc = 0
    delta: dict = {"messages": out_msgs}

    for tc in last.tool_calls or []:
        request_id = state.get("request_id", "")
        tool = tools_by_name.get(tc["name"])
        if tool is None:
            logger.warning(
                "tool_missing request_id=%s tool=%s user_id=%s",
                request_id,
                tc["name"],
                state.get("request_user_id", ""),
            )
            out_msgs.append(
                ToolMessage(
                    content=f'{{"error":"tool {tc["name"]} not implemented yet"}}',
                    tool_call_id=tc["id"],
                    name=tc["name"],
                )
            )
            continue

        # Inject user_id server-side; drop any user_id the LLM might have passed
        args = dict(tc["args"])
        if tc["name"] in INJECT_USER_ID_TOOLS:
            args.pop("user_id", None)
            injected_key = "injected_user_id" if tc["name"] == "set_alert" else "user_id"
            args[injected_key] = state.get("request_user_id", "")

        logger.info(
            "tool_start request_id=%s tool=%s user_id=%s args_keys=%s",
            request_id,
            tc["name"],
            state.get("request_user_id", ""),
            sorted(args.keys()),
        )
        try:
            result = await tool.ainvoke(args)
        except Exception:
            logger.exception(
                "tool_failed request_id=%s tool=%s user_id=%s args_keys=%s",
                request_id,
                tc["name"],
                state.get("request_user_id", ""),
                sorted(args.keys()),
            )
            raise
        logger.info(
            "tool_done request_id=%s tool=%s user_id=%s result_type=%s",
            request_id,
            tc["name"],
            state.get("request_user_id", ""),
            type(result).__name__,
        )
        out_msgs.append(
            ToolMessage(
                content=json.dumps(
                    safe_model_payload(result),
                    ensure_ascii=False,
                    separators=(",", ":"),
                    default=str,
                ),
                tool_call_id=tc["id"],
                name=tc["name"],
            )
        )

        if tc["name"] == "search_flights":
            delta["search_result"] = result
        elif tc["name"] == "match_preferences":
            delta["pref_result"] = result
        elif tc["name"] == "judge_value":
            delta["decision"] = result
        elif tc["name"] == "set_alert":
            delta["alert_result"] = result

        if tc["name"] == "ask_user":
            clarify_inc += 1

    if clarify_inc:
        delta["clarify_count"] = state.get("clarify_count", 0) + clarify_inc

    return delta
