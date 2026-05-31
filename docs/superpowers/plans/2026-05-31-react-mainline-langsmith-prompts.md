# ReAct 主链路 + LangSmith Prompt + 清退 Langfuse 实施计划（Plan 1/4）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把运行时主链路从「纯规则 slot-filling」切换为「ReAct（LLM + function calling）为主、规则版做兜底」，Prompt 改由 LangSmith Hub 管理（三级兜底），并彻底清退 Langfuse。

**Architecture:** `get_graph()` 编译统一图：`bootstrap_session → react_agent ⇄ tool_router → render_response`；当 `react_agent` 的 LLM 调用失败/超时（`llm_failed=True`）时，路由进入现有规则版子链 `fill_intent_slots → {clarify_response | run_slot_search | dynamic_intent_response}`，最终统一由 `render_response`/直接 END 收口。`prompt_loader.load_prompt()` 改为优先从 LangSmith `pull_prompt` 拉取（带进程内 TTL 缓存），缺失时回退本地 `prompts/*.txt`，再回退硬编码默认值。Langfuse 的配置、回调、健康检查、依赖全部移除，可观测性只保留 LangSmith。

**Tech Stack:** Python 3.9 / FastAPI / LangGraph / LangChain / langsmith SDK（已在 requirements）/ pytest + pytest-asyncio。

---

## File Structure

| 文件 | 责任 | 动作 |
|------|------|------|
| `backend/config.py` | 删除 langfuse_* 配置，新增 `langsmith_prompt_prefix` / `prompt_cache_ttl_seconds` | Modify |
| `backend/infrastructure/llm/prompt_loader.py` | LangSmith pull → 本地文件 → 默认值 三级加载 + TTL 缓存 | Modify |
| `backend/application/graph/state.py` | 新增 `llm_failed: bool` 字段 | Modify |
| `backend/application/graph/nodes/react_agent.py` | LLM 调用加超时 + 失败兜底标志 | Modify |
| `backend/application/graph/nodes/render_response.py` | 用最终 AIMessage 文本兜底 `recommendation.text` | Modify |
| `backend/application/graph/factory.py` | `build_graph()` 重构为 ReAct 主 + 规则兜底统一图；新增 `route_after_agent` | Modify |
| `backend/application/services/intent_registry.py` | 修复 sticky intent（兜底路径仍走 match_intent） | Modify |
| `backend/infrastructure/observability/langfuse.py` | 删除 | Delete |
| `backend/infrastructure/observability/guardrail_pusher.py` | 改为日志告警，去掉 langfuse | Modify |
| `backend/main.py` | health 去掉 langfuse_ok | Modify |
| `backend/schemas/common.py` | `HealthResponse` 去掉 langfuse_ok | Modify |
| `backend/requirements.txt` | 删除 langfuse 依赖 | Modify |
| `backend/tests/_fakes/langfuse.py` | 删除 | Delete |
| `backend/tests/observability/test_langfuse_callback.py` | 删除 | Delete |
| `backend/tests/llm/test_prompt_loader.py` | 新增 | Create |
| `backend/tests/graph/test_react_factory.py` | 改写为 ReAct 主 + 兜底断言 | Modify |
| `backend/tests/graph/nodes/test_react_agent.py` | 补 LLM 失败兜底用例 | Modify |
| `backend/tests/services/test_intent_slot_filler.py` | 补 sticky intent 切换用例 | Modify |

---

## Task 1: prompt_loader 接 LangSmith（三级兜底 + TTL 缓存）

**Files:**
- Modify: `backend/config.py:74-90`
- Modify: `backend/infrastructure/llm/prompt_loader.py`
- Test: `backend/tests/llm/test_prompt_loader.py`

- [ ] **Step 1: 在 config.py 删除 langfuse 字段、补 prompt 相关字段**

把 `backend/config.py` 第 74-77 行的 4 个 langfuse 字段删除，并在 langsmith 区块后补充：

```python
    langsmith_api_key: str = Field(default="")
    langsmith_project: str = Field(default="faresniper-dev")
    langsmith_endpoint: str = Field(
        default="https://api.smith.langchain.com",
        alias="LANGSMITH_ENDPOINT",
    )
    langsmith_tracing: bool = Field(default=False, alias="LANGSMITH_TRACING")
    langsmith_prompt_prefix: str = Field(default="faresniper-")
    prompt_cache_ttl_seconds: float = Field(default=300.0)
```

- [ ] **Step 2: 写失败测试**

```python
# backend/tests/llm/test_prompt_loader.py
import backend.infrastructure.llm.prompt_loader as pl


def setup_function():
    pl._CACHE.clear()


def test_falls_back_to_default_when_langsmith_unavailable(monkeypatch):
    monkeypatch.setattr(pl, "_pull_from_langsmith", lambda name: None)
    text = pl.load_prompt("react_agent")
    assert "FareSniper" in text


def test_uses_langsmith_text_when_available(monkeypatch):
    monkeypatch.setattr(pl, "_pull_from_langsmith", lambda name: "HUB PROMPT BODY")
    assert pl.load_prompt("react_agent") == "HUB PROMPT BODY"


def test_caches_within_ttl(monkeypatch):
    calls = {"n": 0}

    def fake_pull(name):
        calls["n"] += 1
        return "HUB"

    monkeypatch.setattr(pl, "_pull_from_langsmith", fake_pull)
    pl.load_prompt("react_agent")
    pl.load_prompt("react_agent")
    assert calls["n"] == 1
```

- [ ] **Step 3: 运行测试确认失败**

Run: `pytest backend/tests/llm/test_prompt_loader.py -v`
Expected: FAIL（`_pull_from_langsmith` / `_CACHE` 不存在）

- [ ] **Step 4: 重写 prompt_loader.py**

```python
from __future__ import annotations

import logging
import time
from pathlib import Path

from backend.config import get_settings

logger = logging.getLogger("faresniper.prompt_loader")

_PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"
_CACHE: dict[str, tuple[str, float]] = {}

_DEFAULTS: dict[str, str] = {
    "react_agent": (
        "你是「FareSniper」机票智能助手，帮用户以最快速度找到值得买的机票。\n"
        "根据用户意图调用合适的工具完成槽位补全、搜索、偏好匹配和价值判断；"
        "信息不全时调用 ask_user 每次只问一个缺失项；闲聊直接回复不调用工具。\n"
        "禁止自己传递 user_id 到 set_alert / get_preferences；该参数由系统注入。"
    ),
}


def _hub_identifier(name: str) -> str:
    prefix = get_settings().langsmith_prompt_prefix
    return f"{prefix}{name}".replace("_", "-")


def _extract_prompt_text(obj) -> str | None:
    """从 LangSmith pull_prompt 返回对象里提取纯文本（兼容 ChatPromptTemplate / PromptTemplate）。"""
    messages = getattr(obj, "messages", None)
    if messages:
        for m in messages:
            template = getattr(getattr(m, "prompt", None), "template", None)
            if template and "system" in type(m).__name__.lower():
                return template
        first_template = getattr(getattr(messages[0], "prompt", None), "template", None)
        if first_template:
            return first_template
    template = getattr(obj, "template", None)
    return template if isinstance(template, str) else None


def _pull_from_langsmith(name: str) -> str | None:
    s = get_settings()
    if not (s.langchain_api_key or s.langsmith_api_key):
        return None
    try:
        from langsmith import Client

        pulled = Client().pull_prompt(_hub_identifier(name))
        return _extract_prompt_text(pulled)
    except Exception:
        logger.warning("langsmith_pull_failed name=%s", name, exc_info=True)
        return None


def load_prompt(name: str) -> str:
    """优先 LangSmith Hub，回退本地 prompts/*.txt，再回退硬编码默认值；进程内 TTL 缓存。"""
    now = time.monotonic()
    cached = _CACHE.get(name)
    if cached and now - cached[1] < get_settings().prompt_cache_ttl_seconds:
        return cached[0]

    text = _pull_from_langsmith(name)
    if not text:
        path = _PROMPTS_DIR / f"{name}.txt"
        if path.exists():
            text = path.read_text(encoding="utf-8").strip()
    if not text:
        text = _DEFAULTS.get(name, f"You are a helpful assistant. [{name}]")

    _CACHE[name] = (text, now)
    return text
```

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest backend/tests/llm/test_prompt_loader.py -v`
Expected: PASS（3 passed）

- [ ] **Step 6: 提交**

```bash
git add backend/config.py backend/infrastructure/llm/prompt_loader.py backend/tests/llm/test_prompt_loader.py
git commit -m "feat(prompt): load prompts from langsmith hub with ttl cache and fallbacks"
```

---

## Task 2: react_agent 加超时与 LLM 失败兜底标志

**Files:**
- Modify: `backend/application/graph/state.py:18-25`
- Modify: `backend/application/graph/nodes/react_agent.py`
- Test: `backend/tests/graph/nodes/test_react_agent.py`

- [ ] **Step 1: 在 WorkflowState 增加 llm_failed 字段**

在 `backend/application/graph/state.py` 的 ReAct 字段区块（第 20 行 `messages` 之后）加一行：

```python
    llm_failed: bool
```

- [ ] **Step 2: 写失败测试**

```python
# 追加到 backend/tests/graph/nodes/test_react_agent.py
import pytest

import backend.application.graph.nodes.react_agent as ra
from langchain_core.messages import HumanMessage


@pytest.mark.asyncio
async def test_react_agent_marks_llm_failed_on_exception(monkeypatch):
    class _Boom:
        def bind_tools(self, tools):
            return self

        async def ainvoke(self, messages):
            raise RuntimeError("llm down")

    monkeypatch.setattr(ra, "load_available_tools", lambda: [])
    monkeypatch.setattr(ra, "build_chat_model", lambda role="agent": _Boom())
    monkeypatch.setattr(ra, "load_prompt", lambda name: "SYS")

    out = await ra.react_agent({"messages": [HumanMessage(content="嗨")], "request_user_id": "u1"})
    assert out.get("llm_failed") is True
    assert "messages" not in out
```

- [ ] **Step 3: 运行测试确认失败**

Run: `pytest backend/tests/graph/nodes/test_react_agent.py::test_react_agent_marks_llm_failed_on_exception -v`
Expected: FAIL（当前会抛 RuntimeError）

- [ ] **Step 4: 重写 react_agent.py**

```python
from __future__ import annotations

import asyncio
import logging

from backend.application.graph.tools import load_available_tools
from backend.infrastructure.llm.models import build_chat_model
from backend.infrastructure.llm.prompt_loader import load_prompt

logger = logging.getLogger("faresniper.graph.react_agent")

LLM_TIMEOUT_SECONDS = 8.0


async def react_agent(state: dict) -> dict:
    """ReAct LLM node: bind tools and invoke the chat model; on failure flag llm_failed for rule fallback."""
    tools = load_available_tools()
    chat = build_chat_model(role="agent")
    if tools:
        chat = chat.bind_tools(tools)

    system = load_prompt("react_agent")
    messages = [{"role": "system", "content": system}, *list(state["messages"])]

    try:
        ai = await asyncio.wait_for(chat.ainvoke(messages), timeout=LLM_TIMEOUT_SECONDS)
    except Exception:
        logger.warning(
            "react_agent_llm_failed user_id=%s", state.get("request_user_id", ""), exc_info=True
        )
        return {"llm_failed": True}

    try:
        from backend.analytics.events import EventName
        from backend.analytics.track import track

        await track(
            EventName.INTENT_PARSED,
            user_id=state.get("request_user_id", ""),
            payload={"intent_complete": bool(ai.tool_calls), "parse_failed": False},
        )
    except Exception:
        pass

    return {"messages": [ai]}
```

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest backend/tests/graph/nodes/test_react_agent.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/application/graph/state.py backend/application/graph/nodes/react_agent.py backend/tests/graph/nodes/test_react_agent.py
git commit -m "feat(graph): react_agent times out and flags llm_failed for rule fallback"
```

---

## Task 3: render_response 用最终 AIMessage 文本兜底回复文案

**Files:**
- Modify: `backend/application/graph/nodes/render_response.py:99-121`
- Test: `backend/tests/graph/nodes/test_render_response.py`

- [ ] **Step 1: 写失败测试**

```python
# 追加到 backend/tests/graph/nodes/test_render_response.py
import pytest
from langchain_core.messages import AIMessage, HumanMessage

from backend.application.graph.nodes.render_response import render_response


@pytest.mark.asyncio
async def test_final_ai_text_becomes_recommendation_text():
    state = {
        "request_user_id": "u1",
        "messages": [HumanMessage(content="你好"), AIMessage(content="我是 FareSniper，告诉我出发地和目的地吧。")],
    }
    out = await render_response(state)
    assert out["response"].recommendation["text"] == "我是 FareSniper，告诉我出发地和目的地吧。"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest backend/tests/graph/nodes/test_render_response.py::test_final_ai_text_becomes_recommendation_text -v`
Expected: FAIL（recommendation 为空 dict）

- [ ] **Step 3: 在 render_response.py 增加 _last_ai_text 并在收口处应用**

在文件末尾（`_async_memory_writeback` 之前）加辅助函数：

```python
def _last_ai_text(state) -> str | None:
    """取最近一条「非工具调用」的 AIMessage 文本，作为 ReAct 最终自然语言回复。"""
    for m in reversed(state.get("messages") or []):
        is_ai = getattr(m, "type", "") == "ai" or m.__class__.__name__ == "AIMessage"
        if not is_ai:
            continue
        if getattr(m, "tool_calls", None):
            return None
        content = getattr(m, "content", "")
        return content.strip() if isinstance(content, str) and content.strip() else None
    return None
```

在 `resp = FrontendResponse(...)` 之前（第 121 行 `recommendation` 三分支构造完成后）插入：

```python
    final_text = _last_ai_text(state)
    if final_text:
        if recommendation:
            recommendation["text"] = final_text
        else:
            recommendation = {
                "action": "watch",
                "text": final_text,
                "confidence": "medium",
                "signals": [],
            }
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest backend/tests/graph/nodes/test_render_response.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/application/graph/nodes/render_response.py backend/tests/graph/nodes/test_render_response.py
git commit -m "feat(graph): render_response prefers final react ai message as recommendation text"
```

---

## Task 4: factory.build_graph 重构为 ReAct 主 + 规则兜底统一图

**Files:**
- Modify: `backend/application/graph/factory.py:78-138`
- Test: `backend/tests/graph/test_react_factory.py`

- [ ] **Step 1: 改写 test_react_factory.py 的结构断言**

把 `test_build_graph_has_slot_filling_nodes` 替换为：

```python
def test_build_graph_wires_react_primary_with_rule_fallback():
    from backend.application.graph.factory import build_graph

    g = build_graph()
    node_names = set(g.get_graph().nodes.keys())
    # ReAct 主链路
    assert {"bootstrap_session", "react_agent", "tool_router", "render_response"} <= node_names
    # 规则兜底子链
    assert {"fill_intent_slots", "clarify_response", "run_slot_search", "dynamic_intent_response"} <= node_names
```

并新增一条「LLM 失败 → 规则兜底澄清」用例：

```python
import pytest
from langchain_core.messages import HumanMessage


def _async_value(v):
    async def _inner(*a, **k):
        return v
    return _inner()


@pytest.mark.asyncio
async def test_llm_failure_falls_back_to_rule_clarify(monkeypatch):
    import backend.application.graph.nodes.bootstrap_session as bs
    import backend.application.graph.nodes.slot_filling as sf
    import backend.application.graph.nodes.react_agent as ra
    from backend.application.services.default_intents import DEFAULT_INTENTS

    monkeypatch.setattr(bs, "load_slots", lambda sid: _async_value(None))
    monkeypatch.setattr(bs, "save_slots", lambda sid, slots: _async_value(None))
    monkeypatch.setattr(sf, "load_intent_registry", lambda: _async_value(DEFAULT_INTENTS))
    # 强制 LLM 失败 → 进入规则兜底
    monkeypatch.setattr(ra, "react_agent", lambda state: _async_value({"llm_failed": True}))

    from backend.application.graph.factory import build_graph, reset_graph_cache

    reset_graph_cache()
    g = build_graph()
    result = await g.ainvoke(
        {
            "messages": [HumanMessage(content="明天去三亚")],
            "request_message": "明天去三亚",
            "request_user_id": "u1",
        }
    )
    assert result["response"].deals == []
    assert result["response"].meta["missing_slots"] == ["origin"]
    assert "从哪里出发" in result["response"].recommendation["text"]
```

> 注：`build_graph` 内部用 `from ... import react_agent` 时取的是模块属性，`monkeypatch.setattr(ra, "react_agent", ...)` 生效的前提是 factory 通过 `ra.react_agent` 间接引用。Step 3 的实现按此方式 import（`import ... react_agent as _ra` 后在节点函数里 `await _ra.react_agent(state)`），保证可被 monkeypatch。

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest backend/tests/graph/test_react_factory.py -v`
Expected: FAIL（旧 build_graph 无 react_agent/tool_router 节点）

- [ ] **Step 3: 重写 factory.py 的 build_graph / route_after_agent**

把 `factory.py` 第 78-138 行（`_compiled_graph` 起至 `reset_graph_cache`）整体替换为：

```python
_compiled_graph = None


def route_after_agent(state: dict) -> str:
    """LLM 失败 → 规则兜底；有工具调用 → 执行工具；否则 → 收口渲染。"""
    if state.get("llm_failed"):
        return "fill_intent_slots"
    messages = state.get("messages") or []
    last = messages[-1] if messages else None
    if last is not None and getattr(last, "tool_calls", None):
        return "tool_router"
    return "render_response"


async def _react_agent_node(state: dict) -> dict:
    # 间接引用，便于测试 monkeypatch
    from backend.application.graph.nodes import react_agent as _ra

    return await _ra.react_agent(state)


def build_graph():
    """ReAct 主链路 + 规则版 slot-filling 兜底的统一编译图。"""
    from backend.application.graph.nodes.bootstrap_session import bootstrap_session
    from backend.application.graph.nodes.render_response import render_response
    from backend.application.graph.nodes.tool_router import tool_router
    from backend.application.graph.nodes.slot_filling import (
        dynamic_intent_response,
        fill_intent_slots,
        route_after_slot_filling,
        run_slot_search,
        slot_clarify_response,
    )

    sg = StateGraph(WorkflowState)
    sg.add_node("bootstrap_session", bootstrap_session)
    sg.add_node("react_agent", _react_agent_node)
    sg.add_node("tool_router", tool_router)
    sg.add_node("render_response", render_response)
    sg.add_node("fill_intent_slots", fill_intent_slots)
    sg.add_node("clarify_response", slot_clarify_response)
    sg.add_node("dynamic_intent_response", dynamic_intent_response)
    sg.add_node("run_slot_search", run_slot_search)

    sg.set_entry_point("bootstrap_session")
    sg.add_edge("bootstrap_session", "react_agent")
    sg.add_conditional_edges(
        "react_agent",
        route_after_agent,
        {
            "tool_router": "tool_router",
            "render_response": "render_response",
            "fill_intent_slots": "fill_intent_slots",
        },
    )
    sg.add_edge("tool_router", "react_agent")
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
```

> `_route_after_react`（旧 84 行）不再需要，可一并删除。`build_search_graph` / `_LazySearchGraph`（旧线性 DAG，1-68 行）保留不动，避免牵连其它依赖。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest backend/tests/graph/test_react_factory.py backend/tests/graph/test_factory_singleton.py -v`
Expected: PASS（如 `test_factory_singleton` 因结构变化失败，按新 `get_graph()` 单例语义同步更新断言）

- [ ] **Step 5: 跑全图相关测试回归**

Run: `pytest backend/tests/graph -v`
Expected: PASS（如 `test_search_graph.py` 断言旧 slot-filling 主链路，改为断言 ReAct 入口；保留兜底子链断言）

- [ ] **Step 6: 提交**

```bash
git add backend/application/graph/factory.py backend/tests/graph
git commit -m "feat(graph): wire react agent as primary with rule-based slot-filling fallback"
```

---

## Task 5: 修复 sticky intent（兜底路径的意图粘滞）

**Files:**
- Modify: `backend/application/services/intent_registry.py:43-80`
- Test: `backend/tests/services/test_intent_slot_filler.py`

- [ ] **Step 1: 写失败测试**

```python
# 追加到 backend/tests/services/test_intent_slot_filler.py
from backend.application.contracts.intent import SlotBundle


def test_strong_new_intent_overrides_sticky_session_intent():
    chit = SlotBundle(intent="chitchat")
    match = match_intent("我要从北京去上海的机票", DEFAULT_INTENTS, chit)
    assert match.intent_name == "search_flight"


def test_slot_only_turn_keeps_session_intent():
    chit = SlotBundle(intent="search_flight")
    match = match_intent("北京", DEFAULT_INTENTS, chit)
    assert match.intent_name == "search_flight"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest backend/tests/services/test_intent_slot_filler.py::test_strong_new_intent_overrides_sticky_session_intent -v`
Expected: FAIL（当前无条件返回 chitchat）

- [ ] **Step 3: 重构 match_intent，新轮强信号优先**

把 `intent_registry.py:43-80` 的 `match_intent` 替换为：

```python
def _best_content_match(
    text: str, definitions: list[IntentDefinition]
) -> IntentMatch | None:
    candidates: list[IntentMatch] = []
    for definition in definitions:
        if not definition.is_active:
            continue
        score, matched_by = _score_intent(text, definition)
        if score > 0:
            candidates.append(
                IntentMatch(
                    intent_name=definition.name,
                    confidence=score,
                    matched_by=matched_by,
                    definition=definition,
                )
            )
    if not candidates:
        return None
    candidates.sort(
        key=lambda item: (item.confidence, item.definition.priority),
        reverse=True,
    )
    return candidates[0]


def match_intent(
    text: str,
    definitions: list[IntentDefinition],
    accumulated: SlotBundle | None = None,
) -> IntentMatch | None:
    normalized = (text or "").strip()
    fresh = _best_content_match(normalized, definitions)

    if accumulated and accumulated.intent:
        session_def = find_intent_definition(definitions, accumulated.intent)
        if session_def:
            # 新一轮带有明确且不同的高置信意图（命中关键词/例句）→ 切换，破除粘滞
            if fresh and fresh.intent_name != accumulated.intent and fresh.confidence >= 0.9:
                return fresh
            return IntentMatch(
                intent_name=session_def.name,
                confidence=0.9,
                matched_by="session",
                definition=session_def,
            )

    return fresh
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest backend/tests/services/test_intent_slot_filler.py -v`
Expected: PASS（含原有用例不回归）

- [ ] **Step 5: 提交**

```bash
git add backend/application/services/intent_registry.py backend/tests/services/test_intent_slot_filler.py
git commit -m "fix(intent): let a strong new-turn intent override sticky session intent"
```

---

## Task 6: 彻底清退 Langfuse

**Files:**
- Delete: `backend/infrastructure/observability/langfuse.py`
- Modify: `backend/infrastructure/observability/guardrail_pusher.py`
- Modify: `backend/main.py:169,178`
- Modify: `backend/schemas/common.py:70`
- Modify: `backend/requirements.txt:22`
- Delete: `backend/tests/_fakes/langfuse.py`
- Delete: `backend/tests/observability/test_langfuse_callback.py`

- [ ] **Step 1: 重写 guardrail_pusher.py（去 langfuse，改日志告警）**

```python
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
```

- [ ] **Step 2: 删除 langfuse 模块与测试桩**

```bash
git rm backend/infrastructure/observability/langfuse.py \
       backend/tests/_fakes/langfuse.py \
       backend/tests/observability/test_langfuse_callback.py
```

- [ ] **Step 3: main.py 去掉 langfuse_ok**

删除 `backend/main.py:169` 的 `langfuse_ok = bool(settings.langfuse_public_key)` 一行，并把 `HealthResponse(...)` 构造（约 178 行）里的 `langfuse_ok=langfuse_ok,` 删除。

- [ ] **Step 4: schemas/common.py 去掉 langfuse_ok 字段**

删除 `backend/schemas/common.py:70` 的 `langfuse_ok: bool = False`。

- [ ] **Step 5: requirements.txt 删除 langfuse**

删除 `backend/requirements.txt:22` 的 `langfuse>=2.50,<3.0`。

- [ ] **Step 6: 全仓搜残留并修干净**

Run: `grep -rn "langfuse\|Langfuse\|langfuse_ok" backend --include="*.py"`
Expected: 无输出。若 `test_health_full.py` / `test_settings_contract.py` / `test_app_metadata.py` 仍断言 `langfuse_ok` 或 langfuse 配置，删除对应断言行。

- [ ] **Step 7: 跑相关回归**

Run: `pytest backend/tests/test_health_full.py backend/tests/test_settings_contract.py backend/tests/observability -v`
Expected: PASS

- [ ] **Step 8: 提交**

```bash
git add -A
git commit -m "chore(obs): remove langfuse; keep langsmith as the only tracer"
```

---

## Task 7: 端到端冒烟与全量回归

- [ ] **Step 1: 全量后端测试**

Run: `pytest backend -q`
Expected: PASS（如个别旧测试锁定「规则版为主链路」的断言，按 ReAct 主 + 规则兜底语义更新，不得跳过）

- [ ] **Step 2: 提交（如有测试调整）**

```bash
git add -A
git commit -m "test: align graph suite with react-primary mainline"
```

---

## Self-Review

- **Spec coverage：** PRD §5.2.2 ReAct（react_agent ⇄ tool_router）✔ Task 4；§5.2.6/§18 LangSmith 追踪保留 ✔（未动 langsmith.py）；§10.1 Prompt 由 Hub 管理 ✔ Task 1；用户「弃用 langfuse」✔ Task 6；上一轮 sticky intent bug ✔ Task 5。
- **Placeholder scan：** 无 TODO/TBD；每个 step 含完整代码或精确命令。
- **Type consistency：** `llm_failed`（state）↔ `route_after_agent` ↔ react_agent 返回值一致；`recommendation` dict 形状与 `FrontendResponse.recommendation` 一致；`match_intent` 返回 `IntentMatch` 一致。

## Execution Handoff

见末尾统一说明。
