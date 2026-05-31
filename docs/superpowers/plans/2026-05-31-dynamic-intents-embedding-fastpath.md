# 动态意图注册表 + Embedding 快速路 实施计划（Plan 4/4）

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**前置依赖：** Plan 1（ReAct 主链路、`react_agent` 用 `load_prompt("react_agent")`、`bootstrap_session` 是入口节点）。

**Goal:** 落地 PRD §9.2.6 的「动态意图」与「Embedding 快速路」：意图例句存向量、相似度 > 0.85 命中时向消息注入意图预判提示；bootstrap 时把激活意图的描述/槽位动态渲染进 ReAct System Prompt 的 `{intent_definitions}` 占位；Admin 添加例句时自动生成 embedding。

**Architecture:** `intent_examples.embedding`（现为 JSONB）存归一化向量。查询时 `fast_intent_match(text)` 取库内例句向量，在 Python 侧做余弦相似度（不引入 pgvector 扩展依赖；生产可平滑切换 pgvector，见 Task 2 说明）。`bootstrap_session` 调 `fast_intent_match` 命中则向 `state["messages"]` 追加一条 `SystemMessage` 预判提示，并把 `load_intent_registry()` 的激活意图渲染成 `intent_definitions_text` 存入 state；`react_agent` 用它填充 System Prompt 的 `{intent_definitions}`。Admin `/intents/{name}/examples` 写入时调用 embedding 模型生成向量。

**Tech Stack:** DashScope/OpenAI 兼容 embeddings API / numpy（已随 scrapers 依赖）/ pytest。

---

## File Structure

| 文件 | 责任 | 动作 |
|------|------|------|
| `backend/infrastructure/llm/embeddings.py` | `embed(text) -> list[float]`（OpenAI 兼容 embeddings） | Create |
| `backend/infrastructure/db/intent_registry_repo.py` | 新增 `list_examples_with_embeddings()` / `set_example_embedding()` | Modify |
| `backend/application/services/intent_examples.py` | `fast_intent_match()` 余弦相似 + `render_intent_definitions()` | Create |
| `backend/application/graph/nodes/bootstrap_session.py` | 注入快速路预判 + intent_definitions_text | Modify |
| `backend/application/graph/nodes/react_agent.py` | System Prompt 填充 `{intent_definitions}` | Modify |
| `backend/api/admin_intents.py` | 添加例句时生成 embedding | Modify |
| `backend/tests/services/test_intent_examples.py` | 新增 | Create |
| `backend/tests/graph/nodes/test_bootstrap_session.py` | 补快速路注入断言 | Modify |

---

## Task 1: embeddings.embed()

**Files:**
- Create: `backend/infrastructure/llm/embeddings.py`
- Test: `backend/tests/llm/test_embeddings.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/llm/test_embeddings.py
import pytest

import backend.infrastructure.llm.embeddings as emb


@pytest.mark.asyncio
async def test_embed_returns_empty_without_api_key(monkeypatch):
    monkeypatch.setattr(emb.settings, "model_api_key", "")
    assert await emb.embed("北京到上海") == []


@pytest.mark.asyncio
async def test_embed_uses_client(monkeypatch):
    class _Resp:
        data = [type("D", (), {"embedding": [0.1, 0.2, 0.3]})()]

    class _Embeddings:
        async def create(self, **kw):
            return _Resp()

    class _Client:
        embeddings = _Embeddings()

    monkeypatch.setattr(emb.settings, "model_api_key", "sk-x")
    monkeypatch.setattr(emb, "_async_client", lambda: _Client())
    assert await emb.embed("北京到上海") == [0.1, 0.2, 0.3]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest backend/tests/llm/test_embeddings.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 embeddings.py**

```python
from __future__ import annotations

import logging

from backend.config import settings

logger = logging.getLogger("faresniper.embeddings")

EMBED_MODEL = "text-embedding-v3"


def _async_client():
    from openai import AsyncOpenAI

    return AsyncOpenAI(api_key=settings.model_api_key, base_url=settings.model_base_url)


async def embed(text: str) -> list[float]:
    """生成文本向量；缺 API key 或异常时返回空列表（调用方自行降级）。"""
    if not settings.model_api_key or not text.strip():
        return []
    try:
        resp = await _async_client().embeddings.create(model=EMBED_MODEL, input=text)
        return list(resp.data[0].embedding)
    except Exception:
        logger.warning("embed_failed", exc_info=True)
        return []
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest backend/tests/llm/test_embeddings.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/infrastructure/llm/embeddings.py backend/tests/llm/test_embeddings.py
git commit -m "feat(llm): add embeddings.embed via openai-compatible endpoint"
```

---

## Task 2: 例句向量读写仓储方法

**Files:**
- Modify: `backend/infrastructure/db/intent_registry_repo.py`
- Test: `backend/tests/infra/test_intent_examples_repo.py`

> 设计选择：`embedding` 列保持 JSONB（存 `list[float]`），相似度在 Python 侧计算。理由：避免引入 pgvector 扩展与运维成本，MVP 例句量级（每意图 ~10-30 条）Python 余弦足够快。**生产切换 pgvector**：把列改 `vector(1536)`、`fast_intent_match` 改 `ORDER BY embedding <=> :q LIMIT 1`，接口不变。

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/infra/test_intent_examples_repo.py
import pytest

from backend.infrastructure.db.intent_registry_repo import (
    IntentRegistry, IntentExample, set_example_embedding, list_examples_with_embeddings,
)
from backend.infrastructure.db.base import get_session


@pytest.mark.asyncio
async def test_set_and_list_embeddings(seeded_pg):
    async with get_session() as s:
        s.add(IntentRegistry(name="search_flight", description="查机票", handler_name="search_flights"))
        s.add(IntentExample(id=1, intent_name="search_flight", example_text="北京到上海机票"))
        await s.commit()

    await set_example_embedding(1, [0.1, 0.2, 0.3])
    rows = await list_examples_with_embeddings()
    assert any(r["intent_name"] == "search_flight" and r["embedding"] == [0.1, 0.2, 0.3] for r in rows)
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest backend/tests/infra/test_intent_examples_repo.py -v`
Expected: FAIL（函数不存在）

- [ ] **Step 3: 在 intent_registry_repo.py 追加两个函数**

```python
async def set_example_embedding(example_id: int, vector: list[float]) -> None:
    async with get_session() as session:
        row = await session.get(IntentExample, example_id)
        if row is not None:
            row.embedding = vector
            await session.commit()


async def list_examples_with_embeddings() -> list[dict]:
    async with get_session() as session:
        rows = (await session.execute(select(IntentExample))).scalars().all()
        return [
            {"id": r.id, "intent_name": r.intent_name, "example_text": r.example_text, "embedding": r.embedding}
            for r in rows
            if r.embedding
        ]
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest backend/tests/infra/test_intent_examples_repo.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/infrastructure/db/intent_registry_repo.py backend/tests/infra/test_intent_examples_repo.py
git commit -m "feat(db): read/write intent example embeddings"
```

---

## Task 3: fast_intent_match（余弦）+ render_intent_definitions

**Files:**
- Create: `backend/application/services/intent_examples.py`
- Test: `backend/tests/services/test_intent_examples.py`

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/services/test_intent_examples.py
import pytest

import backend.application.services.intent_examples as ie
from backend.application.contracts.intent_registry import IntentDefinition


@pytest.mark.asyncio
async def test_fast_match_returns_intent_above_threshold(monkeypatch):
    async def fake_examples():
        return [{"id": 1, "intent_name": "search_flight", "example_text": "北京到上海机票", "embedding": [1.0, 0.0]}]

    monkeypatch.setattr(ie, "list_examples_with_embeddings", fake_examples)
    monkeypatch.setattr(ie, "embed", lambda text: _coro([1.0, 0.0]))

    match = await ie.fast_intent_match("我要北京飞上海")
    assert match is not None
    assert match["intent_name"] == "search_flight"
    assert match["confidence"] > 0.85


@pytest.mark.asyncio
async def test_fast_match_none_below_threshold(monkeypatch):
    async def fake_examples():
        return [{"id": 1, "intent_name": "search_flight", "example_text": "x", "embedding": [1.0, 0.0]}]

    monkeypatch.setattr(ie, "list_examples_with_embeddings", fake_examples)
    monkeypatch.setattr(ie, "embed", lambda text: _coro([0.0, 1.0]))  # 正交 → 相似度 0
    assert await ie.fast_intent_match("天气怎么样") is None


def test_render_intent_definitions():
    defs = [IntentDefinition(name="search_flight", description="查机票", required_slots=["origin", "destination", "depart_date"], handler_name="search_flights")]
    text = ie.render_intent_definitions(defs)
    assert "search_flight" in text and "查机票" in text


def _coro(v):
    async def _inner():
        return v
    return _inner()
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest backend/tests/services/test_intent_examples.py -v`
Expected: FAIL（模块不存在）

- [ ] **Step 3: 实现 intent_examples.py**

```python
from __future__ import annotations

import math

from backend.application.contracts.intent_registry import IntentDefinition
from backend.infrastructure.db.intent_registry_repo import list_examples_with_embeddings
from backend.infrastructure.llm.embeddings import embed

FAST_PATH_THRESHOLD = 0.85


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


async def fast_intent_match(text: str) -> dict | None:
    """对例句向量做余弦匹配；最高分 > 阈值则返回意图预判。"""
    query_vec = await embed(text)
    if not query_vec:
        return None
    examples = await list_examples_with_embeddings()
    best: dict | None = None
    best_score = 0.0
    for ex in examples:
        score = _cosine(query_vec, ex["embedding"])
        if score > best_score:
            best_score = score
            best = ex
    if best and best_score >= FAST_PATH_THRESHOLD:
        return {"intent_name": best["intent_name"], "confidence": round(best_score, 4), "source": "embedding"}
    return None


def render_intent_definitions(definitions: list[IntentDefinition]) -> str:
    """把激活意图渲染为 ReAct System Prompt 中 {intent_definitions} 的文本块。"""
    lines = []
    for d in definitions:
        if not d.is_active:
            continue
        slots = "、".join(d.required_slots) if d.required_slots else "无"
        lines.append(f"- {d.name}: {d.description}（必填槽位：{slots}）")
    return "\n".join(lines)
```

- [ ] **Step 4: 运行测试确认通过**

Run: `pytest backend/tests/services/test_intent_examples.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/application/services/intent_examples.py backend/tests/services/test_intent_examples.py
git commit -m "feat(intent): embedding fast-path match + intent-definitions renderer"
```

---

## Task 4: bootstrap 注入快速路预判 + 动态意图定义

**Files:**
- Modify: `backend/application/graph/nodes/bootstrap_session.py:44-63`
- Modify: `backend/application/graph/nodes/react_agent.py:15-16`
- Modify: `backend/application/graph/state.py`
- Test: `backend/tests/graph/nodes/test_bootstrap_session.py`

- [ ] **Step 1: state 增加 intent_definitions_text 字段**

在 `state.py` ReAct 字段区加：

```python
    intent_definitions_text: str
```

- [ ] **Step 2: 写失败测试**

```python
# 追加到 backend/tests/graph/nodes/test_bootstrap_session.py
import pytest

import backend.application.graph.nodes.bootstrap_session as bs
from backend.application.contracts.intent import SlotBundle
from backend.application.contracts.intent_registry import IntentDefinition


@pytest.mark.asyncio
async def test_bootstrap_injects_fast_path_hint(monkeypatch):
    monkeypatch.setattr(bs, "load_slots", lambda sid: _coro(SlotBundle()))
    monkeypatch.setattr(bs, "save_slots", lambda sid, slots: _coro(None))
    monkeypatch.setattr(bs, "load_intent_registry", lambda: _coro([
        IntentDefinition(name="search_flight", description="查机票", handler_name="search_flights"),
    ]))
    monkeypatch.setattr(bs, "fast_intent_match", lambda text: _coro({"intent_name": "search_flight", "confidence": 0.92, "source": "embedding"}))

    out = await bs.bootstrap_session({"request_session_id": "s1", "request_message": "北京到上海", "request_user_id": "u1"})
    assert any("search_flight" in getattr(m, "content", "") for m in out.get("messages", []))
    assert "search_flight" in out["intent_definitions_text"]


def _coro(v):
    async def _inner():
        return v
    return _inner()
```

- [ ] **Step 3: 运行测试确认失败**

Run: `pytest backend/tests/graph/nodes/test_bootstrap_session.py::test_bootstrap_injects_fast_path_hint -v`
Expected: FAIL（无注入逻辑）

- [ ] **Step 4: 改写 bootstrap_session（第 44-63 行的 ReAct 版函数）**

在文件顶部 import：

```python
from langchain_core.messages import SystemMessage  # noqa: E402
from backend.application.services.intent_examples import fast_intent_match, render_intent_definitions  # noqa: E402
from backend.application.services.intent_registry import load_intent_registry  # noqa: E402
```

把 `bootstrap_session` 函数体改为：

```python
async def bootstrap_session(state: dict) -> dict:
    """Initialize session: alloc session_id, restore slots, inject intent fast-path + dynamic tool definitions."""
    sid = state.get("request_session_id") or f"s_{uuid.uuid4().hex[:12]}"
    try:
        slots = await load_slots(sid) or SlotBundle()
        await save_slots(sid, slots)
    except Exception:
        logger.exception("session_store_unavailable request_id=%s session_id=%s", state.get("request_id", ""), sid)
        slots = SlotBundle()

    definitions = await load_intent_registry()
    intent_definitions_text = render_intent_definitions(definitions)

    new_messages: list = []
    text = state.get("request_message", "") or ""
    try:
        fast = await fast_intent_match(text)
    except Exception:
        fast = None
    if fast:
        new_messages.append(SystemMessage(
            content=f"[系统提示] 用户意图已预判为 {fast['intent_name']}（置信度 {fast['confidence']:.2f}），请直接提取槽位或执行工具。"
        ))

    return {
        "request_session_id": sid,
        "accumulated_slots": slots,
        "intent_definitions": definitions,
        "intent_definitions_text": intent_definitions_text,
        "messages": new_messages,
        "clarify_count": state.get("clarify_count", 0),
        "fallback_triggered": state.get("fallback_triggered", False),
        "errors": state.get("errors", []),
    }
```

> `messages` 用 `add_messages` reducer，返回的 `new_messages` 会**追加**到入口已有的 HumanMessage 之后，不覆盖。

- [ ] **Step 5: react_agent 填充 {intent_definitions}**

把 `react_agent.py` 第 15 行 `system = load_prompt("react_agent")` 改为：

```python
    system = load_prompt("react_agent")
    if "{intent_definitions}" in system:
        system = system.replace("{intent_definitions}", state.get("intent_definitions_text", ""))
```

- [ ] **Step 6: 运行测试确认通过**

Run: `pytest backend/tests/graph/nodes/test_bootstrap_session.py -v`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add backend/application/graph/nodes/bootstrap_session.py backend/application/graph/nodes/react_agent.py backend/application/graph/state.py backend/tests/graph/nodes/test_bootstrap_session.py
git commit -m "feat(graph): inject embedding fast-path hint and dynamic intent definitions at bootstrap"
```

---

## Task 5: Admin 添加例句时生成 embedding

**Files:**
- Modify: `backend/api/admin_intents.py`
- Test: `backend/tests/api/test_admin_intents.py`（若不存在则新增）

- [ ] **Step 1: 写失败测试**

```python
# backend/tests/api/test_admin_intents.py
import pytest

import backend.api.admin_intents as ai


@pytest.mark.asyncio
async def test_add_example_generates_embedding(monkeypatch):
    saved = {}

    async def fake_insert(intent_name, example_text):
        return 7  # new example id

    async def fake_embed(text):
        return [0.5, 0.5]

    async def fake_set(example_id, vector):
        saved["id"] = example_id
        saved["vec"] = vector

    monkeypatch.setattr(ai, "insert_example", fake_insert)
    monkeypatch.setattr(ai, "embed", fake_embed)
    monkeypatch.setattr(ai, "set_example_embedding", fake_set)

    await ai._add_example_with_embedding("search_flight", "去三亚的机票")
    assert saved["id"] == 7
    assert saved["vec"] == [0.5, 0.5]
```

- [ ] **Step 2: 运行测试确认失败**

Run: `pytest backend/tests/api/test_admin_intents.py -v`
Expected: FAIL（`_add_example_with_embedding` / `insert_example` 不存在）

- [ ] **Step 3: 在 intent_registry_repo.py 增加 insert_example**

```python
async def insert_example(intent_name: str, example_text: str) -> int:
    async with get_session() as session:
        row = IntentExample(intent_name=intent_name, example_text=example_text)
        session.add(row)
        await session.commit()
        await session.refresh(row)
        return row.id
```

- [ ] **Step 4: 在 admin_intents.py 增加 helper 并在 POST examples 路由调用**

文件顶部 import：

```python
from backend.infrastructure.db.intent_registry_repo import insert_example, set_example_embedding
from backend.infrastructure.llm.embeddings import embed
from backend.application.services.intent_registry import invalidate_intent_registry_cache
```

新增并在「批量添加例句」路由里对每条例句调用：

```python
async def _add_example_with_embedding(intent_name: str, example_text: str) -> None:
    example_id = await insert_example(intent_name, example_text)
    vector = await embed(example_text)
    if vector:
        await set_example_embedding(example_id, vector)
```

> 添加/激活意图后调用 `await invalidate_intent_registry_cache()`，使 60s TTL 立即失效（PRD §9.2.6 管理接口 `cache/invalidate`）。

- [ ] **Step 5: 运行测试确认通过**

Run: `pytest backend/tests/api/test_admin_intents.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/api/admin_intents.py backend/infrastructure/db/intent_registry_repo.py backend/tests/api/test_admin_intents.py
git commit -m "feat(admin): generate embeddings when adding intent examples"
```

---

## Task 6: 全量回归

- [ ] **Step 1:** Run: `pytest backend/tests/graph backend/tests/services/test_intent_examples.py backend/tests/llm backend/tests/api/test_admin_intents.py -q` → Expected: PASS

---

## Self-Review

- **Spec coverage：** §9.2.6 识别层动态（DB 写入 → 60s 生效）✔ Task 4/5；embedding 快速路 > 0.85 注入预判 ✔ Task 3/4；动态 tool 定义注入 System Prompt ✔ Task 4；Admin 例句自动 embedding + 缓存失效 ✔ Task 5。
- **Placeholder scan：** 无；pgvector vs JSON 取舍已显式说明，接口对生产可平滑切换。
- **Type consistency：** `fast_intent_match` 返回 dict 键（intent_name/confidence/source）↔ bootstrap 消费一致；`render_intent_definitions` 输出 ↔ react_agent `{intent_definitions}` 替换一致；`embed`/`set_example_embedding`/`list_examples_with_embeddings` 向量类型 `list[float]` 全程一致。

## Execution Handoff

见下方统一说明。
