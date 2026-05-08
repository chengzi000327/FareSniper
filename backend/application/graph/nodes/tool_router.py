from __future__ import annotations

from langchain_core.messages import ToolMessage

from backend.application.graph.tools import load_available_tools

INJECT_USER_ID_TOOLS = {"set_alert", "get_preferences"}


async def tool_router(state: dict) -> dict:
    """Execute all tool calls in the last AI message and populate state fields."""
    tools_by_name = {t.name: t for t in load_available_tools()}
    last = state["messages"][-1]
    out_msgs: list = []
    clarify_inc = 0
    delta: dict = {"messages": out_msgs}

    for tc in last.tool_calls or []:
        tool = tools_by_name.get(tc["name"])
        if tool is None:
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
            args["injected_user_id"] = state.get("request_user_id", "")

        result = await tool.ainvoke(args)
        out_msgs.append(
            ToolMessage(content=str(result), tool_call_id=tc["id"], name=tc["name"])
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
