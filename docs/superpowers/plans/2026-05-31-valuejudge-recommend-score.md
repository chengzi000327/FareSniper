# ValueJudge 接入 + recommend_score + 节假日 实施计划（Plan 3/4）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**前置依赖：** Plan 1（ReAct 主链路 + tool_router 已把 `judge_value` 结果写入 `state["decision"]`）。

**Goal:** 补齐 PRD §9.6 / §10.3 / §11.1 的「值得买」闭环：新增 `judge_value` 工具（包 `services/value_judge.py` 的 ValueJudge，prompt 走 LangSmith），把 `is_holiday`（含端午）传入判断，并在收口处对 deals 计算 `recommend_score` 与排序。

**Architecture:** ReAct Agent 搜索后调用 `judge_value()` 工具 → `tool_router` 把返回的 `DecisionResult` 写入 `state["decision"]`。`judge_value` 内部：从 `state["search_result"]` 取航班，用 `services/holiday.is_holiday` 生成 `is_holiday_map`，用 `services/preference_matcher`（若有 pref）生成匹配，调 `ValueJudge.judge()` 得到每航班 signals+advice，聚合为整单 `DecisionResult`。`render_response` 在已有 deals 上调用 `recommend_scorer.sort_deals` 写 `recommend_score` 并排序。

**Tech Stack:** LangChain tools / 既有 `services/value_judge.py`、`services/holiday.py`、`services/recommend_scorer.py` / pytest。

---

## File Structure

| 文件 | 责任 | 动作 |
|------|------|------|
| `backend/application/graph/tools/judge_value.py` | `judge_value` 工具，产出 DecisionResult | Create |
| `backend/application/graph/tools/__init__.py` | 注册已就绪的 judge_value（已在列表，确认加载） | Verify |
| `backend/application/graph/nodes/render_response.py` | 收口处对 deals 调用 sort_deals + 写 recommend_score/signals/verdict | Modify |
| `backend/services/value_judge.py` | system prompt 改为 `load_prompt("value_judge")` | Modify |
| `backend/tests/graph/tools/test_judge_value.py` | 新增 | Create |
| `backend/tests/graph/nodes/test_render_response.py` | 补 recommend_score 排序断言 | Modify |
| `backend/tests/services/test_value_judge.py` | 补 prompt 来源用例（若已存在则补充） | Modify |

---

## Task 1: judge_value 工具

**Files:**
- Create: `backend/application/graph/tools/judge_value.py`
- Test: `backend/tests/graph/tools/test_judge_value.py`

> `tool_router.py:80` 已有 `elif tc["name"] == "judge_value": delta["decision"] = result`，故工具返回的 `DecisionResult` 会自动落到 `state["decision"]`，被 `render_response` 第 100-106 行消费。

> **入参约定：** ReAct Agent 调 `judge_value()` 无参；工具内部从入参 `deals`/`pref` 读取（由 LLM 从上文 search_flights/get_preferences 的 ToolMessage 内容传入）。为稳妥，工具签名接受可选 `deals` 与 `pref`，缺省时返回中性结论。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/graph/tools/test_judge_value.py
import pytest

from backend.application.contracts.decision import DecisionResult, RecommendedAction
import backend.application.graph.tools.judge_value as jv


@pytest.mark.asyncio
async def test_judge_value_flags_historical_low(monkeypatch):
    # ValueJudge 启发式：lowest 远低于 history_avg_90d → 历史低价
    deals = [{"flight_no": "HU7833", "lowest_price": 389, "history_avg_90d": 584, "depart_date": "2026-06-19"}]
    result = await jv.judge_value.ainvoke({"deals": deals, "pref": {}})
    assert isinstance(result, DecisionResult)
    assert "历史低价" in result.signals
    assert result.action in {RecommendedAction.buy_now, RecommendedAction.watch}
    assert result.text


@pytest.mark.asyncio
async def test_judge_value_neutral_when_no_deals():
    result = await jv.judge_value.ainvoke({"deals": [], "pref": {}})
    assert result.action == RecommendedAction.watch
    assert result.signals == []
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest backend/tests/graph/tools/test_judge_value.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 judge_value.py**

```python
from __future__ import annotations

from typing import Any

from langchain_core.tools import tool

from backend.application.contracts.decision import DecisionResult, RecommendedAction
from backend.infrastructure.llm.models import build_chat_model
from backend.services.holiday import is_holiday
from backend.services.value_judge import ValueJudge


def _aggregate(per_flight: list[dict[str, Any]]) -> DecisionResult:
    if not per_flight:
        return DecisionResult(action=RecommendedAction.watch, confidence="low",
                              text="价格正常，可继续关注", signals=[])
    best = per_flight[0]
    signals = list(best.get("signals", []))
    advice = best.get("advice", "价格正常，可继续关注")
    if "历史低价" in signals:
        action = RecommendedAction.buy_now
        confidence = "high"
    elif signals:
        action = RecommendedAction.watch
        confidence = "medium"
    else:
        action = RecommendedAction.watch
        confidence = "low"
    return DecisionResult(action=action, confidence=confidence, text=advice, signals=signals)


@tool
async def judge_value(deals: list[dict] | None = None, pref: dict | None = None) -> DecisionResult:
    """综合价格、历史均价、节假日与偏好，输出值得买信号与一句话建议。"""
    deals = deals or []
    if not deals:
        return DecisionResult(action=RecommendedAction.watch, confidence="low",
                              text="价格正常，可继续关注", signals=[])

    is_holiday_map = {d.get("depart_date", ""): is_holiday(d.get("depart_date", "")) for d in deals}
    budget = (pref or {}).get("budget")
    pref_results = [
        {
            "flight_no": d.get("flight_no", ""),
            "matched": bool(budget and d.get("lowest_price", d.get("price", 0)) <= budget),
            "reasons": ["在你的心理价位以内"] if budget and d.get("lowest_price", d.get("price", 0)) <= budget else [],
        }
        for d in deals
    ]

    judge = ValueJudge(llm_client=build_chat_model(role="judge"), model="qwen-plus")
    per_flight = await judge.judge(deals, pref_results, is_holiday_map)
    return _aggregate(per_flight)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest backend/tests/graph/tools/test_judge_value.py -v`
Expected: PASS（启发式分支不依赖真实 LLM）

> 若 `ValueJudge.judge` 的启发式未产出「历史低价」，按 `services/value_judge.py` 既有阈值（差值 >15%）核对；389 vs 584 差值 33% 应触发。

- [ ] **Step 5: 验证工具已被注册**

Run: `python -c "from backend.application.graph.tools import load_available_tools; print([t.name for t in load_available_tools()])"`
Expected: 输出包含 `judge_value`

- [ ] **Step 6: 提交**

```bash
git add backend/application/graph/tools/judge_value.py backend/tests/graph/tools/test_judge_value.py
git commit -m "feat(tool): judge_value produces DecisionResult with holiday + preference signals"
```

---

## Task 2: render_response 接入 recommend_score 与排序

**Files:**
- Modify: `backend/application/graph/nodes/render_response.py:23-52`
- Test: `backend/tests/graph/nodes/test_render_response.py`

- [ ] **Step 1: 写失败测试**

```python
# 追加到 backend/tests/graph/nodes/test_render_response.py
import pytest

from backend.application.graph.nodes.render_response import render_response


@pytest.mark.asyncio
async def test_deals_get_recommend_score_and_sorted_by_total():
    state = {
        "request_user_id": "u1",
        "search_result": {
            "deals": [
                {"flight_no": "A", "price": 600, "tax": 0, "baggage_fee": 0, "stops": 0, "history_avg_90d": 700},
                {"flight_no": "B", "price": 400, "tax": 0, "baggage_fee": 0, "stops": 0, "history_avg_90d": 700},
            ],
            "source": "cache",
        },
    }
    out = await render_response(state)
    deals = out["response"].deals
    assert deals[0]["flight_no"] == "B"  # 总价低者在前
    assert deals[0]["recommend_score"]   # 已写入非空字符串
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest backend/tests/graph/nodes/test_render_response.py::test_deals_get_recommend_score_and_sorted_by_total -v`
Expected: FAIL（deals 未排序、无 recommend_score）

- [ ] **Step 3: 在 render_response 的 deals 构造后插入排序**

在 `render_response.py` 中、`prices = _extract_prices(...)`（第 52 行）之前，对 ReAct dict 路径产出的 `deals` 调用排序：

```python
    if deals:
        from backend.services.recommend_scorer import sort_deals

        pref_results = []
        if isinstance(pref_result, dict):
            pref_results = pref_result.get("filtered", []) + pref_result.get("boosted", [])
        deals = sort_deals(deals, pref_results)
```

> `sort_deals` 会就地写 `recommend_score` 与 `_boost` 并返回排序后的列表（见 `recommend_scorer.py:37-60`）。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest backend/tests/graph/nodes/test_render_response.py -v`
Expected: PASS（含 Plan 1 的 final-text 用例不回归）

- [ ] **Step 5: 提交**

```bash
git add backend/application/graph/nodes/render_response.py backend/tests/graph/nodes/test_render_response.py
git commit -m "feat(graph): compute recommend_score and sort deals in render_response"
```

---

## Task 3: ValueJudge prompt 改由 LangSmith 管理

**Files:**
- Modify: `backend/services/value_judge.py:8-29`
- Test: `backend/tests/services/test_value_judge.py`

- [ ] **Step 1: 写失败测试**

```python
# 追加到 backend/tests/services/test_value_judge.py
import backend.services.value_judge as vj


def test_value_judge_uses_loaded_prompt(monkeypatch):
    monkeypatch.setattr(vj, "load_prompt", lambda name: "PULLED VALUE JUDGE PROMPT")
    assert vj._system_prompt() == "PULLED VALUE JUDGE PROMPT"
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest backend/tests/services/test_value_judge.py::test_value_judge_uses_loaded_prompt -v`
Expected: FAIL（无 `_system_prompt` / `load_prompt` 引用）

- [ ] **Step 3: 在 value_judge.py 改为从 load_prompt 取**

在文件顶部 import：

```python
from backend.infrastructure.llm.prompt_loader import load_prompt
```

把模块级 `_SYSTEM_PROMPT = """..."""`（第 8-29 行）保留为 `_FALLBACK_SYSTEM_PROMPT`（同样内容），新增：

```python
def _system_prompt() -> str:
    text = load_prompt("value_judge")
    return text if text and "[value_judge]" not in text else _FALLBACK_SYSTEM_PROMPT
```

并把 `_judge_via_llm` 内引用 `_SYSTEM_PROMPT` 的地方改为调用 `_system_prompt()`。

> 注：`prompt_loader._DEFAULTS` 暂无 `value_judge` 键，故未配置 LangSmith/本地文件时 `load_prompt` 返回占位串 `"You are a helpful assistant. [value_judge]"`，被上面的判断挡回 `_FALLBACK_SYSTEM_PROMPT`，保证离线行为不变。可选：把完整 value_judge prompt 也加入 `_DEFAULTS`。

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest backend/tests/services/test_value_judge.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/services/value_judge.py backend/tests/services/test_value_judge.py
git commit -m "feat(judge): source ValueJudge system prompt from langsmith with fallback"
```

---

## Task 4: 端到端验证「值得买」闭环

- [ ] **Step 1:** Run: `pytest backend/tests/graph backend/tests/services/test_value_judge.py -q` → Expected: PASS
- [ ] **Step 2:** 如个别旧断言因新增 recommend_score 字段变化，更新断言后提交。

---

## Self-Review

- **Spec coverage：** §9.6 信号体系（历史低价/心理价位/节假日不入 signals 但入 advice）✔ Task 1（复用既有 ValueJudge 约束）；§11.1 recommend_score 公式 + deals 排序 ✔ Task 2（复用 recommend_scorer）；§10.3 ValueJudge prompt ✔ Task 3；端午等节假日 ✔（`services/holiday.py` 已含端午，Task 1 接入）。
- **Placeholder scan：** 无；离线/无 LLM 行为均有明确兜底分支。
- **Type consistency：** `judge_value` 返回 `DecisionResult` ↔ `tool_router` `delta["decision"]` ↔ `render_response` `decision.action.value/.text/.confidence/.signals`（contracts/decision.py:25-31）一致。

## Execution Handoff

见末尾统一说明。
