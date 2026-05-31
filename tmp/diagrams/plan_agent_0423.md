# FareSniper v2.0 LangGraph 迁移 — 第一期操作手册
# 对齐 plan_backend_reset0414 战略方向，精简至可落地的最小闭环
# 最后更新：2026-04-29

---

## 概述

**战略来源**：`plan_backend_reset0414.md`（完整架构蓝图，共 8 阶段）

**本文档范围**：第一期，覆盖 0414 的阶段 1-5，**只迁移 `/api/search` 主链路**。

**核心原则**（直接来自 0414）：
- 先立契约，再立 graph
- graph runtime 是后端唯一编排权威，不是"旧代码外面的壳"
- 旧代码只作为迁移参考，不作为长期兼容层
- 每阶段都有测试覆盖，通过测试才算完成

**目录结构**（来自 0414 section 3.1）：
```
backend/
  application/
    contracts/          ← Phase 0：先立契约（本期重点）
    context/            ← Phase 1：最小 session 装配
    graph/
      nodes/            ← Phase 2：SearchGraph 节点
      state.py
      factory.py
      runtime.py
    adapters/           ← Phase 2：各层 adapter
  infrastructure/
    llm/                ← Phase 1：LangChain 模型工厂
```

**不做（明确延后）**：
- Langfuse prompt 监控（0414 阶段 7）
- Progressive skill loading（0414 阶段 6）
- Context budget 管理（0414 section 6.6）
- RecommendationGraph、MemoryGraph（第二期）
- `/api/chat` 及其他入口切换

**不使用 `USE_LANGGRAPH` feature flag**：0414 明确"旧代码不作为长期兼容层"，新 graph 在独立目录开发，测试通过后直接切换 `/api/search`，不做灰度开关。

---

## 当前代码基线（迁移前）

```
POST /api/search
└── SearchService.search()                        [search_service.py:56]
    ├── _load_session_history()                   [search_service.py:242]
    ├── IntentParser.parse()                      [intent_parser.py:55]
    │   ├── _parse_via_llm() → UnifiedLLMClient
    │   └── _parse_heuristic() → 正则 fallback
    ├── is_intent_complete() → _clarify_response() [search_service.py:277]
    ├── asyncio.gather(
    │   ├── _fetch_flights()                      [search_service.py:200]
    │   └── _get_preferences()                    [search_service.py:230]
    │   )
    ├── run_preference_match()                    [preference_matcher.py]
    ├── is_holiday() + sort_deals()               [holiday.py / recommend_scorer.py]
    ├── ValueJudge.judge()                        [value_judge.py:37]
    └── asyncio.create_task(learn_from_search())  [memory_learner.py]
```

旧 `services/` 模块在新 graph 端到端通过前**不删不改**，只作为逻辑参考。

---

## Step -1：修复测试基座（Phase 0 前置条件）

> 现有 `backend/tests/conftest.py` 的 `autouse` fixture 访问 `settings.memory_file`，
> 但 `backend/config.py` 的 `Settings` 中不存在该字段，导致 `pytest` 在 fixture setup
> 阶段就崩溃，**所有新增测试都无法运行**。必须先修复，再执行 Phase 0。

修改 `backend/tests/conftest.py`，删除或改造 `tmp_memory_file` fixture：

```python
# backend/tests/conftest.py
# 删除以下整个 fixture（settings.memory_file 字段不存在于当前 config.py）
# @pytest.fixture(autouse=True)
# def tmp_memory_file(tmp_path: Path):
#     original = settings.memory_file
#     settings.memory_file = tmp_path / "memory.json"
#     yield settings.memory_file
#     settings.memory_file = original

# 同时把 client fixture 的依赖从 tmp_memory_file 改为只依赖 tmp_path（或无参数）
@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    from asgi_lifespan import LifespanManager
    from backend.main import create_app

    app = create_app()
    async with LifespanManager(app, startup_timeout=30) as manager:
        transport = ASGITransport(app=manager.app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
```

**验证：**
```bash
python -m pytest backend/tests/test_schemas.py -v   # 用一个简单测试确认 fixture 不再崩溃
```

---

## Phase 0：建立 Contracts（先立契约）

> 对应 0414 阶段 1。**这是所有 graph 节点的语言定义，必须最先完成。**

### Step 0.1 创建目录骨架

```bash
mkdir -p backend/application/contracts
mkdir -p backend/application/context
mkdir -p backend/application/graph/nodes
mkdir -p backend/application/adapters
mkdir -p backend/infrastructure/llm
touch backend/application/__init__.py
touch backend/application/contracts/__init__.py
touch backend/application/context/__init__.py
touch backend/application/graph/__init__.py
touch backend/application/graph/nodes/__init__.py
touch backend/application/adapters/__init__.py
touch backend/infrastructure/__init__.py
touch backend/infrastructure/llm/__init__.py
mkdir -p backend/tests/contracts
mkdir -p backend/tests/graph
touch backend/tests/__init__.py
touch backend/tests/contracts/__init__.py
touch backend/tests/graph/__init__.py
```

---

### Step 0.2 新建 `backend/application/contracts/base.py`

```python
"""所有契约模型的基类，禁止额外字段、启用严格校验。"""
from pydantic import BaseModel, ConfigDict


class BaseContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=False)
```

---

### Step 0.3 新建 `backend/application/contracts/workflow.py`

```python
"""graph 入口契约：WorkflowRequest / WorkflowError。"""
from __future__ import annotations
from enum import Enum
from .base import BaseContract


class WorkflowErrorCode(str, Enum):
    parse_failed        = "parse_failed"
    intent_incomplete   = "intent_incomplete"
    clarify_exceeded    = "clarify_exceeded"
    datasource_timeout  = "datasource_timeout"
    schema_validation   = "schema_validation"
    llm_timeout         = "llm_timeout"
    memory_write_error  = "memory_write_error"
    unknown             = "unknown"


class WorkflowRequest(BaseContract):
    user_id: str
    session_id: str | None = None
    message: str


class WorkflowError(BaseContract):
    code: WorkflowErrorCode
    message: str
    node: str | None = None        # 出错的节点名
    retryable: bool = False
```

---

### Step 0.4 新建 `backend/application/contracts/intent.py`

契约示例来自 0414 section 5.3。

```python
"""意图解析输出契约：NormalizedIntent。"""
from __future__ import annotations
from enum import Enum
from .base import BaseContract


class IntentConfidence(str, Enum):
    high   = "high"
    medium = "medium"
    low    = "low"


class LocationRef(BaseContract):
    city: str | None = None
    iata_code: str | None = None
    confidence: float = 1.0


class DateWindow(BaseContract):
    start_date: str | None = None   # YYYY-MM-DD
    end_date: str | None = None
    is_flexible: bool = False


class IntentConstraintType(str, Enum):
    avoid_red_eye   = "avoid_redeye"
    direct_only     = "direct_only"
    prefer_morning  = "prefer_morning"


class IntentConstraint(BaseContract):
    type: IntentConstraintType
    value: bool = True


class NormalizedIntent(BaseContract):
    origin: LocationRef | None = None
    destination: LocationRef | None = None
    date_window: DateWindow | None = None
    budget_cny: int | None = None
    constraints: list[IntentConstraint] = []
    ambiguities: list[str] = []
    intent_confidence: IntentConfidence = IntentConfidence.medium
    raw_text: str = ""
    parse_failed: bool = False


def is_intent_complete(intent: NormalizedIntent) -> bool:
    """必填槽位：origin、destination、date_window.start_date 均不为 None。"""
    return (
        intent.origin is not None and intent.origin.city is not None
        and intent.destination is not None and intent.destination.city is not None
        and intent.date_window is not None and intent.date_window.start_date is not None
    )
```

---

### Step 0.5 新建 `backend/application/contracts/search.py`

```python
"""航班搜索结果契约：FlightCandidate / FlightSearchResult。"""
from __future__ import annotations
from .base import BaseContract


class PlatformPrice(BaseContract):
    platform: str
    price: int
    url: str = ""
    lowest: bool = False


class FlightCandidate(BaseContract):
    flight_no: str
    airline: str
    depart_time: str        # HH:MM（字段名对齐 mock_flights 和 DealCardDto）
    arrive_time: str
    duration: str
    stops: int = 0
    depart_date: str        # YYYY-MM-DD
    origin_city: str = ""
    origin_code: str = ""
    destination_city: str = ""
    destination_code: str = ""
    prices: list[PlatformPrice] = []
    price: int = 0          # = lowest_price，供 sort_deals(f.get("price")) 使用
    lowest_price: int = 0
    history_avg_90d: float | None = None
    history_low_90d: float | None = None
    is_holiday: bool = False
    # 下游节点写入
    signals: list[str] = []
    verdict: str = ""
    recommend_score: str = "0.0"
    confidence: str = "low"
    has_baggage: bool = True
    tax: int = 0
    baggage_fee: int = 0
    booking_url: str = ""
    h5_fallback_url: str = ""


class FlightSearchResult(BaseContract):
    candidates: list[FlightCandidate] = []
    source: str = "mock"
    query_origin: str = ""
    query_destination: str = ""
    query_date: str = ""
```

---

### Step 0.6 新建 `backend/application/contracts/preference.py`

```python
"""偏好匹配结果契约。"""
from __future__ import annotations
from .base import BaseContract


class PreferenceMatchItem(BaseContract):
    flight_no: str
    matched: bool = False
    boost: bool = False        # 常去城市，影响排序但不展示文案
    reasons: list[str] = []    # 直接用于前端展示，≤3 条


class PreferenceMatchResult(BaseContract):
    items: list[PreferenceMatchItem] = []
```

---

### Step 0.7 新建 `backend/application/contracts/decision.py`

```python
"""决策契约：DecisionSignal / DecisionResult。"""
from __future__ import annotations
from enum import Enum
from .base import BaseContract


class RecommendedAction(str, Enum):
    buy_now = "buy_now"
    watch   = "watch"
    skip    = "skip"


class DecisionFactor(BaseContract):
    factor_type: str
    summary: str
    weight: float = 1.0


class DecisionResult(BaseContract):
    action: RecommendedAction
    confidence: str = "low"
    text: str                       # 前端 AI 建议文案，≤20字
    signals: list[str] = []
    decision_factors: list[DecisionFactor] = []
    branch_reason: str = ""


class FrontendResponse(BaseContract):
    """直接对应 PRD SearchResponseDto，供前端消费。"""
    user_id: str
    query: dict | None = None
    deals: list[dict] = []
    analysis: dict = {}
    recommendation: dict = {}
    meta: dict = {}
```

---

### Step 0.8 先写契约测试

新建 `backend/tests/contracts/test_contracts.py`：

```python
import pytest
from backend.application.contracts.workflow import WorkflowRequest, WorkflowError, WorkflowErrorCode
from backend.application.contracts.intent import NormalizedIntent, LocationRef, DateWindow, is_intent_complete
from backend.application.contracts.search import FlightCandidate, FlightSearchResult
from backend.application.contracts.preference import PreferenceMatchResult
from backend.application.contracts.decision import DecisionResult, RecommendedAction


def test_workflow_request_requires_user_id_and_message():
    req = WorkflowRequest(user_id="u1", message="北京去三亚")
    assert req.user_id == "u1"


def test_workflow_request_rejects_extra_fields():
    with pytest.raises(Exception):
        WorkflowRequest(user_id="u1", message="test", unknown_field="x")


def test_workflow_error_code_is_enum():
    err = WorkflowError(code=WorkflowErrorCode.parse_failed, message="解析失败")
    assert err.code == "parse_failed"


def test_normalized_intent_complete():
    intent = NormalizedIntent(
        origin=LocationRef(city="北京", iata_code="BJS"),
        destination=LocationRef(city="三亚", iata_code="SYX"),
        date_window=DateWindow(start_date="2026-05-01", end_date="2026-05-05"),
    )
    assert is_intent_complete(intent) is True


def test_normalized_intent_incomplete_missing_origin():
    intent = NormalizedIntent(
        destination=LocationRef(city="三亚"),
        date_window=DateWindow(start_date="2026-05-01"),
    )
    assert is_intent_complete(intent) is False


def test_flight_candidate_has_required_fields():
    f = FlightCandidate(
        flight_no="HU7833", airline="海南航空",
        depart_time="09:30", arrive_time="14:20", duration="4h50m",
        depart_date="2026-05-01", price=389, lowest_price=389,
    )
    assert f.flight_no == "HU7833"


def test_decision_result_enum_action():
    d = DecisionResult(action=RecommendedAction.buy_now, text="建议现在买")
    assert d.action == "buy_now"
```

**验证：**
```bash
python -m pytest backend/tests/contracts/ -v
# 预期：全部通过
```

**Phase 0 完成标志**：
- 所有契约测试通过
- 后续 graph 节点将以这些 Schema 为唯一输入输出类型

---

## Phase 1：基础设施（依赖 + LangChain 模型工厂 + 最小 Context Pipeline）

### Step 1.1 安装依赖

```bash
cd /Users/chengzi/Documents/FareSniper/backend
pip install "langgraph>=0.3.0" "langchain>=0.3.0" "langchain-community>=0.3.0" \
            "langsmith>=0.1.0" "langchain-openai>=0.2.0"
```

在 `requirements.txt` 末尾追加：
```
langgraph>=0.3.0
langchain>=0.3.0
langchain-community>=0.3.0
langsmith>=0.1.0
langchain-openai>=0.2.0
```

**验证：**
```bash
python -c "import langgraph; import langchain; import langsmith; print('依赖 OK')"
```

---

### Step 1.2 更新 `backend/config.py`

在 `Settings` 末尾追加：

```python
    # ── LangSmith（只需环境变量，LangGraph 自动读取） ───────────────────────
    langchain_tracing: bool = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
    langchain_api_key: str = os.getenv("LANGCHAIN_API_KEY", "")
    langchain_project: str = os.getenv("LANGCHAIN_PROJECT", "faressniper-dev")
    langchain_endpoint: str = os.getenv("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")
```

在 `settings = Settings()` 之后追加：

```python
if settings.langchain_tracing and settings.langchain_api_key:
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_API_KEY", settings.langchain_api_key)
    os.environ.setdefault("LANGCHAIN_PROJECT", settings.langchain_project)
    os.environ.setdefault("LANGCHAIN_ENDPOINT", settings.langchain_endpoint)
```

---

### Step 1.3 更新 `backend/.env.example`

```bash
# ── LangSmith 观测 ────────────────────────────────────────────────────
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=ls__your_key_here
LANGCHAIN_PROJECT=faressniper-dev
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

---

### Step 1.4 新建 `backend/infrastructure/llm/models.py`

```python
"""LangChain ChatModel 工厂，替换 UnifiedLLMClient。"""
from __future__ import annotations
from backend.config import settings


def get_intent_model():
    return _build(settings.model_intent)


def get_judge_model():
    return _build(settings.model_judge)


def _build(model_name: str):
    if not settings.model_api_key or settings.model_api_key in ("", "mock"):
        from langchain_core.language_models.fake_chat_models import FakeListChatModel
        return FakeListChatModel(responses=[
            '{"origin":{"city":"北京","iata_code":"BJS"},'
            '"destination":{"city":"三亚","iata_code":"SYX"},'
            '"date_window":{"start_date":"2026-05-01","end_date":"2026-05-05"},'
            '"budget_cny":null,"constraints":[],"parse_failed":false}'
        ])
    if "qwen" in model_name.lower():
        try:
            from langchain_community.chat_models.tongyi import ChatTongyi
            return ChatTongyi(model=model_name, dashscope_api_key=settings.model_api_key)
        except ImportError:
            pass
    from langchain_openai import ChatOpenAI
    return ChatOpenAI(
        model=model_name,
        api_key=settings.model_api_key,
        base_url=settings.model_base_url,
        temperature=0.2,
    )
```

---

### Step 1.5 新建 `backend/application/context/assembler.py`

> 0414 阶段 2 精简版：只装配 session_history + user_memory，**暂不做 context budget / permissions / skill metadata**。

```python
"""最小 ContextEnvelope 装配器（第一期）。
完整装配顺序见 plan_backend_reset0414.md section 6.2。
第一期只实现：session_history + memory_facts，其余 block 占位留空。
"""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class ContextEnvelope:
    session_history: list[dict] = field(default_factory=list)   # 最近 10 条对话
    memory_facts: dict = field(default_factory=dict)             # 用户偏好快照
    current_message: str = ""
    assembly_trace: list[str] = field(default_factory=list)
    # 延后实现的 blocks（占位）
    # system_blocks / developer_blocks / permission_blocks / skill_blocks / budget_report


async def assemble_context(
    *,
    session_id: str | None,
    user_id: str,
    message: str,
    session_factory,
    redis_client,
) -> ContextEnvelope:
    """从 DB / Redis 加载上下文，返回 ContextEnvelope。"""
    history = await _load_session_history(session_id, session_factory)
    memory_facts = await _load_memory_facts(user_id, session_factory)

    return ContextEnvelope(
        session_history=history,
        memory_facts=memory_facts,
        current_message=message,
        assembly_trace=["session_history", "memory_facts", "current_message"],
    )


async def _load_session_history(session_id: str | None, session_factory) -> list[dict]:
    if not session_id or not session_factory:
        return []
    try:
        from sqlalchemy import select
        from backend.db.models import ChatHistory
        async with session_factory() as db:
            stmt = (
                select(ChatHistory)
                .where(ChatHistory.session_id == session_id)
                .order_by(ChatHistory.created_at.asc())
                .limit(10)
            )
            rows = (await db.execute(stmt)).scalars().all()
            return [{"role": r.role, "content": r.content} for r in rows]
    except Exception:
        return []


async def _load_memory_facts(user_id: str, session_factory) -> dict:
    if not session_factory:
        return {}
    try:
        async with session_factory() as db:
            from backend.memory.long_term import LongTermMemory
            return await LongTermMemory(db).get_preferences(user_id) or {}
    except Exception:
        return {}
```

---

## Phase 2：SearchGraph 实现

### Step 2.1 新建 `backend/application/graph/state.py`

> 对应 0414 section 3.3 WorkflowState，字段以本项目 MVP 为界精简。

```python
"""SearchGraph 运行时状态，每次 invoke 全新初始化，无 checkpointer。"""
from __future__ import annotations
from typing import Any
from typing_extensions import TypedDict

from backend.application.contracts.intent import NormalizedIntent
from backend.application.contracts.search import FlightSearchResult
from backend.application.contracts.preference import PreferenceMatchResult
from backend.application.contracts.decision import DecisionResult, FrontendResponse
from backend.application.contracts.workflow import WorkflowError
from backend.application.context.assembler import ContextEnvelope


class WorkflowState(TypedDict):
    # ── 入口（api 层写入） ────────────────────────────────────────────
    request_user_id: str
    request_session_id: str | None
    request_message: str
    # ── 上下文（bootstrap_session 节点写入） ─────────────────────────
    context: ContextEnvelope | None
    clarify_count: int
    # ── 意图（parse_intent 节点写入） ────────────────────────────────
    intent: NormalizedIntent | None
    # ── 搜索结果（fetch_flights 节点写入） ───────────────────────────
    search_result: FlightSearchResult | None
    # ── 偏好匹配（match_preferences 节点写入） ────────────────────────
    pref_result: PreferenceMatchResult | None
    # ── 价值判断（judge_value 节点写入） ─────────────────────────────
    decision: DecisionResult | None
    # ── 最终响应（render_response 节点写入） ─────────────────────────
    response: FrontendResponse | None
    # ── 错误（任意节点写入） ─────────────────────────────────────────
    errors: list[WorkflowError]
    # ── 基础设施（api 层注入，不序列化到 LangSmith） ──────────────────
    _session_factory: Any
    _redis_client: Any
```

---

### Step 2.2 新建 `backend/application/graph/nodes/bootstrap_session.py`

```python
"""节点 A：bootstrap_session_context。
从 ContextEnvelope 装配器获取 session_history + memory_facts。
对应 0414 节点 A。
"""
from __future__ import annotations
from backend.application.graph.state import WorkflowState
from backend.application.context.assembler import assemble_context


async def bootstrap_session_context(state: WorkflowState) -> WorkflowState:
    ctx = await assemble_context(
        session_id=state["request_session_id"],
        user_id=state["request_user_id"],
        message=state["request_message"],
        session_factory=state.get("_session_factory"),
        redis_client=state.get("_redis_client"),
    )
    clarify_count = await _get_clarify_count(
        state["request_session_id"], state.get("_redis_client")
    )
    return {**state, "context": ctx, "clarify_count": clarify_count}


async def _get_clarify_count(session_id: str | None, redis_client) -> int:
    if not session_id or not redis_client:
        return 0
    try:
        val = await redis_client.get(f"clarify:{session_id}")
        return int(val) if val else 0
    except Exception:
        return 0
```

---

### Step 2.3 新建 `backend/application/graph/nodes/parse_intent.py`

```python
"""节点 B：parse_user_intent。
LLM 解析意图 → NormalizedIntent（0414 契约）。
"""
from __future__ import annotations
import json
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from backend.application.graph.state import WorkflowState
from backend.application.contracts.intent import NormalizedIntent, is_intent_complete
from backend.application.contracts.workflow import WorkflowError, WorkflowErrorCode
from backend.infrastructure.llm.models import get_intent_model

_SYSTEM_PROMPT = """你是一个机票查询助手，专注于从用户输入中提取出行意图。

从用户输入中提取：origin（出发城市）、destination（目的地）、date_window（出行日期）、budget_cny（预算）、constraints（约束列表）。

## 判断逻辑
1. origin.city：出发城市中文名，未提及为null
2. destination.city：目的地城市中文名，未提及为null
3. date_window.start_date："五一"=2026-05-01，"下周末"=最近周六，"清明"=2026-04-04

## 约束识别
- "不要太早"/"不要红眼" → constraints: [{"type":"avoid_redeye","value":true}]
- "直飞" → constraints: [{"type":"direct_only","value":true}]
- "尽量早点到" → constraints: [{"type":"prefer_morning","value":true}]

## 城市→机场代码（常用）
北京=BJS 上海=SHA 广州=CAN 成都=CTU 三亚=SYX 杭州=HGH 重庆=CKG 西安=XIY

## 输出格式（严格 JSON，符合 NormalizedIntent schema）
{"origin":{"city":"北京","iata_code":"BJS"},"destination":{"city":"三亚","iata_code":"SYX"},
"date_window":{"start_date":"2026-05-01","end_date":"2026-05-05"},"budget_cny":600,
"constraints":[{"type":"avoid_redeye","value":true}],"parse_failed":false}

不确定字段填null，只输出JSON。"""

_prompt = ChatPromptTemplate.from_messages([
    ("system", _SYSTEM_PROMPT),
    MessagesPlaceholder(variable_name="history", optional=True),
    ("human", "{message}"),
])


def _build_chain():
    model = get_intent_model()
    try:
        return _prompt | model.with_structured_output(NormalizedIntent)
    except Exception:
        # FakeListChatModel fallback：手动解析（json 已在模块顶层 import）
        class _JsonParser:
            async def ainvoke(self, inputs):
                raw = await (_prompt | model).ainvoke(inputs)
                try:
                    data = json.loads(raw.content if hasattr(raw, "content") else raw)
                    return NormalizedIntent(**data)
                except Exception:
                    return NormalizedIntent(parse_failed=True)
        return _JsonParser()


_intent_chain = _build_chain()

_CLARIFY_PROMPTS = {
    "origin":       "请问您从哪个城市出发？",
    "destination":  "请问目的地是哪里？",
    "date":         "请问什么时间出发？",
}


async def parse_user_intent(state: WorkflowState) -> WorkflowState:
    ctx = state.get("context")
    history = [{"role": m["role"], "content": m["content"]}
               for m in (ctx.session_history if ctx else [])[-4:]]
    try:
        intent = await _intent_chain.ainvoke({
            "message": state["request_message"],
            "history": history,
        })
    except Exception as e:
        intent = NormalizedIntent(parse_failed=True)

    errors = list(state.get("errors") or [])
    if intent.parse_failed:
        errors.append(WorkflowError(
            code=WorkflowErrorCode.parse_failed,
            message="意图解析失败", node="parse_user_intent",
        ))
    return {**state, "intent": intent, "errors": errors}


# ── 条件边路由函数 ────────────────────────────────────────────────────
def route_after_intent(state: WorkflowState) -> str:
    intent = state.get("intent")
    if not intent or intent.parse_failed:
        return "clarify"
    if is_intent_complete(intent):
        return "complete"
    return "clarify"
```

---

### Step 2.4 新建 `backend/application/graph/nodes/clarify.py`

```python
"""澄清响应节点：意图不完整时返回追问。"""
from __future__ import annotations
from datetime import datetime, timezone
from backend.application.graph.state import WorkflowState
from backend.application.contracts.decision import FrontendResponse


_PROMPTS = {
    "origin":       "请问您从哪个城市出发？",
    "destination":  "请问目的地是哪里？",
    "date":         "请问什么时间出发？",
}


async def clarify_response(state: WorkflowState) -> WorkflowState:
    intent = state.get("intent")
    count = (state.get("clarify_count") or 0) + 1

    if count >= 2:
        text = "填一下这几项吧"
    elif not intent or not (intent.origin and intent.origin.city):
        text = _PROMPTS["origin"]
    elif not (intent.destination and intent.destination.city):
        text = _PROMPTS["destination"]
    else:
        text = _PROMPTS["date"]

    await _save_clarify_count(state, count)

    now = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    resp = FrontendResponse(
        user_id=state["request_user_id"],
        query=None, deals=[],
        analysis={"match_score": 0, "within_budget": False, "matched_preferences": []},
        recommendation={"action": "watch", "text": text, "confidence": "low", "signals": []},
        meta={"generated_at": now, "fallback_mode": False, "clarify_count": count},
    )
    return {**state, "response": resp, "clarify_count": count}


async def _save_clarify_count(state: WorkflowState, count: int) -> None:
    redis = state.get("_redis_client")
    session_id = state.get("request_session_id")
    if not redis or not session_id:
        return
    try:
        await redis.setex(f"clarify:{session_id}", 1800, count)
    except Exception:
        pass
```

---

### Step 2.5 新建 `backend/application/graph/nodes/fetch_flights.py`

```python
"""节点 F1：run_flight_search。
查价 + 读偏好，对应 0414 section 4.1 F1。
"""
from __future__ import annotations
import asyncio
from backend.application.graph.state import WorkflowState
from backend.application.contracts.search import FlightSearchResult, FlightCandidate, PlatformPrice
from backend.application.contracts.intent import NormalizedIntent, IntentConstraintType
from backend.data_sources.mock_flights import get_mock_flights


async def run_flight_search(state: WorkflowState) -> WorkflowState:
    intent: NormalizedIntent = state["intent"]
    user_id = state["request_user_id"]
    session_factory = state.get("_session_factory")

    raw_flights, _ = await asyncio.gather(
        _fetch(intent),
        asyncio.sleep(0),   # 占位，第二期接真实多平台爬虫
    )

    # 构建 FlightSearchResult（契约化）
    origin_city = intent.origin.city if intent.origin else ""
    dest_city = intent.destination.city if intent.destination else ""
    date = intent.date_window.start_date if intent.date_window else ""

    candidates = [_to_candidate(f) for f in raw_flights]
    result = FlightSearchResult(
        candidates=candidates,
        source="mock",
        query_origin=origin_city,
        query_destination=dest_city,
        query_date=date,
    )
    return {**state, "search_result": result}


async def _fetch(intent: NormalizedIntent) -> list[dict]:
    origin = intent.origin.city if intent.origin else ""
    dest = intent.destination.city if intent.destination else ""
    date = intent.date_window.start_date if intent.date_window else ""
    try:
        flights = get_mock_flights(origin, dest, date)
    except Exception:
        flights = []
    # direct_only 过滤
    direct_only = any(
        c.type == IntentConstraintType.direct_only for c in intent.constraints
    )
    if direct_only:
        flights = [f for f in flights if f.get("stops", 0) == 0]
    return flights


def _to_candidate(raw: dict) -> FlightCandidate:
    # mock_flights 的 prices[*] 用 "name" 键（不是 "platform"），转存到 PlatformPrice.platform
    prices = [
        PlatformPrice(
            platform=p.get("name", p.get("platform", "")),
            price=p["price"],
            url=p.get("url", ""),
            lowest=p.get("lowest", False),
        )
        for p in raw.get("prices", [])
    ]
    lowest = raw.get("lowest_price", raw.get("price", 0))
    return FlightCandidate(
        flight_no=raw.get("flight_no", ""),
        airline=raw.get("airline", ""),
        # mock_flights 用 "depart_time"/"arrive_time"，与 DealCardDto 对齐
        depart_time=raw.get("depart_time", raw.get("dep_time", "")),
        arrive_time=raw.get("arrive_time", raw.get("arr_time", "")),
        duration=raw.get("duration", ""),
        stops=raw.get("stops", 0),
        depart_date=raw.get("depart_date", ""),
        origin_city=raw.get("origin_city", ""),
        origin_code=raw.get("origin_code", ""),
        destination_city=raw.get("destination_city", ""),
        destination_code=raw.get("destination_code", ""),
        prices=prices,
        price=raw.get("price", lowest),   # sort_deals 用 f.get("price")
        lowest_price=lowest,
        history_avg_90d=raw.get("history_avg_90d"),
        history_low_90d=raw.get("history_low_90d"),
        tax=raw.get("tax", 0),
        baggage_fee=raw.get("baggage_fee", 0),
        has_baggage=raw.get("has_baggage", True),
        booking_url=raw.get("booking_url", ""),
        h5_fallback_url=raw.get("h5_fallback_url", ""),
    )
```

---

### Step 2.6 新建 `backend/application/graph/nodes/match_preferences.py`

```python
"""节点 F2：run_preference_match（纯工程，复用现有函数）。"""
from __future__ import annotations
from backend.application.graph.state import WorkflowState
from backend.application.contracts.preference import PreferenceMatchResult, PreferenceMatchItem
from backend.application.contracts.search import FlightCandidate
from backend.services.holiday import is_holiday
from backend.services.recommend_scorer import sort_deals


async def run_preference_match(state: WorkflowState) -> WorkflowState:
    search_result = state.get("search_result")
    if not search_result or not search_result.candidates:
        return {**state, "pref_result": PreferenceMatchResult()}

    ctx = state.get("context")
    memory_facts = ctx.memory_facts if ctx else {}

    # 复用现有工程函数（不重写）
    raw_flights = [c.model_dump() for c in search_result.candidates]
    from backend.services.preference_matcher import run_preference_match as _match
    raw_pref = _match(raw_flights, memory_facts)

    # 注入 is_holiday + recommend_score 到候选
    for c in search_result.candidates:
        c.is_holiday = is_holiday(c.depart_date)

    raw_sorted = sort_deals(raw_flights, raw_pref)
    # 按排序结果重排 candidates，并同步 recommend_score（sort_deals 写回 dict 不自动更新契约对象）
    order = {f["flight_no"]: i for i, f in enumerate(raw_sorted)}
    score_map = {f["flight_no"]: f.get("recommend_score", "0.0") for f in raw_sorted}
    search_result.candidates.sort(key=lambda c: order.get(c.flight_no, 999))
    for c in search_result.candidates:
        c.recommend_score = score_map.get(c.flight_no, "0.0")

    items = [
        PreferenceMatchItem(
            flight_no=p.get("flight_no", ""),
            matched=p.get("matched", False),
            boost=p.get("boost", False),
            reasons=p.get("reasons", []),
        )
        for p in raw_pref
    ]
    return {**state, "pref_result": PreferenceMatchResult(items=items)}
```

---

### Step 2.7 新建 `backend/application/graph/nodes/judge_value.py`

```python
"""节点 G：synthesize_decision（LLM 价值判断）。"""
from __future__ import annotations
import json
from pydantic import BaseModel
from langchain_core.prompts import ChatPromptTemplate
from backend.application.graph.state import WorkflowState
from backend.application.contracts.decision import (
    DecisionResult, RecommendedAction, DecisionFactor
)
from backend.infrastructure.llm.models import get_judge_model

_SYSTEM_PROMPT = """你是机票价值判断助手。

对每张票输出：signals（值得买信号列表）、advice（≤20字建议）。

判断规则：
1. lowest_price < history_avg_90d × 0.85 → 触发"历史低价"
2. preference_matched=true → 触发"符合心理价位"
3. is_holiday=true → advice 可提及节假日，但不写入 signals

返回对象（with_structured_output 模式）：
{"items":[{"flight_no":"HU7833","signals":["历史低价"],"advice":"建议现在买，比均价低43%"}]}

advice ≤20字。"""

_prompt = ChatPromptTemplate.from_messages([
    ("system", _SYSTEM_PROMPT),
    ("human", "{payload}"),
])


class _JudgeItem(BaseModel):
    flight_no: str
    signals: list[str] = []
    advice: str = ""

class _JudgeList(BaseModel):
    items: list[_JudgeItem] = []


def _build_chain():
    model = get_judge_model()
    try:
        return _prompt | model.with_structured_output(_JudgeList)
    except Exception:
        from langchain_core.output_parsers import StrOutputParser
        class _FallbackParser:
            async def ainvoke(self, inputs):
                return None
        return _FallbackParser()


_judge_chain = _build_chain()


async def synthesize_decision(state: WorkflowState) -> WorkflowState:
    search_result = state.get("search_result")
    pref_result = state.get("pref_result")
    if not search_result or not search_result.candidates:
        decision = DecisionResult(action=RecommendedAction.skip, text="暂无航班数据")
        return {**state, "decision": decision}

    pref_map = {p.flight_no: p for p in (pref_result.items if pref_result else [])}
    payload = []
    for c in search_result.candidates[:5]:  # 最多判断前5条
        pref = pref_map.get(c.flight_no)
        payload.append({
            "flight_no": c.flight_no,
            "lowest_price": c.lowest_price,
            "history_avg_90d": c.history_avg_90d,
            "is_holiday": c.is_holiday,
            "preference_matched": pref.matched if pref else False,
        })

    try:
        result = await _judge_chain.ainvoke(
            {"payload": json.dumps(payload, ensure_ascii=False)}
        )
        if result and hasattr(result, "items"):
            judge_items = result.items
        else:
            raise ValueError("fallback")
    except Exception:
        from backend.services.value_judge import ValueJudge
        raw_flights = [c.model_dump() for c in search_result.candidates[:5]]
        raw_pref = [p.model_dump() for p in (pref_result.items if pref_result else [])]
        # _judge_heuristic 按 depart_date 查 is_holiday，键必须用 depart_date（不是 flight_no）
        is_holiday_map = {c.depart_date: c.is_holiday for c in search_result.candidates}
        raw_judged = ValueJudge(llm_client=None)._judge_heuristic(
            raw_flights, raw_pref, is_holiday_map
        )
        judge_items = [_JudgeItem(**j) for j in raw_judged]

    # 写回 signals + verdict 到 candidates
    judge_map = {j.flight_no: j for j in judge_items}
    for c in search_result.candidates:
        jud = judge_map.get(c.flight_no)
        if jud:
            c.signals = jud.signals
            c.verdict = jud.advice

    # 取 best candidate 决定 action
    best = search_result.candidates[0] if search_result.candidates else None
    top_signals = best.signals if best else []
    has_hist_low = "历史低价" in top_signals
    within_budget = "符合心理价位" in top_signals
    if has_hist_low and within_budget:
        action, confidence = RecommendedAction.buy_now, "high"
    elif has_hist_low or within_budget:
        action, confidence = RecommendedAction.watch, "medium"
    else:
        action, confidence = RecommendedAction.watch, "low"

    factors = [DecisionFactor(factor_type=s, summary=s, weight=1.0) for s in top_signals]
    decision = DecisionResult(
        action=action, confidence=confidence,
        text=best.verdict if best else "价格正常，可继续关注",
        signals=top_signals,
        decision_factors=factors,
        branch_reason=action.value,
    )
    return {**state, "decision": decision}
```

---

### Step 2.8 新建 `backend/application/graph/nodes/render_response.py`

```python
"""节点 H：render_response，组装 FrontendResponse + 异步触发记忆写回。"""
from __future__ import annotations
import asyncio, uuid
from datetime import datetime, timezone
from backend.application.graph.state import WorkflowState
from backend.application.contracts.decision import FrontendResponse


def _now():
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


async def render_response(state: WorkflowState) -> WorkflowState:
    search_result = state.get("search_result")
    decision = state.get("decision")
    intent = state.get("intent")
    pref_result = state.get("pref_result")

    # deals：将 FlightCandidate 转为前端 DTO（对应 PRD 7.1 DealCardDto）
    deals = []
    if search_result:
        pref_map = {p.flight_no: p for p in (pref_result.items if pref_result else [])}
        for c in search_result.candidates:
            pref = pref_map.get(c.flight_no)
            deal = c.model_dump()
            deal["id"] = f"deal-{c.flight_no}-{c.depart_date}"
            deal["system_id"] = f"{c.flight_no}-{c.depart_date}"
            deal["platform"] = next((p.platform for p in c.prices if p.lowest), "")
            deal["origin_city"] = c.origin_city or (intent.origin.city if intent and intent.origin else "")
            deal["destination_city"] = c.destination_city or (intent.destination.city if intent and intent.destination else "")
            # depart_time / arrive_time 已在 FlightCandidate.model_dump() 中，此处显式确保
            deal["depart_time"] = c.depart_time
            deal["arrive_time"] = c.arrive_time
            deal["price"] = c.lowest_price
            # matched_reasons / boost 不在 DealCardDto schema 内，model_validate 会静默丢弃，故不写入
            # 转换 prices 为 PriceItemDto 格式（name/price/lowest），PlatformPrice 用 platform 字段
            deal["prices"] = [
                {"name": p["platform"], "price": p["price"], "lowest": p.get("lowest", False)}
                for p in deal.get("prices", [])
            ]
            deals.append(deal)

    # analysis
    prices = [c.lowest_price for c in (search_result.candidates if search_result else [])]
    pref_reasons: list[str] = []
    if pref_result:
        for p in pref_result.items:
            pref_reasons.extend(p.reasons)

    # 计算 avg_90d / lower_than_avg（与旧 SearchService 行为保持一致）
    avg_90d_vals = [c.history_avg_90d for c in (search_result.candidates if search_result else [])
                    if c.history_avg_90d]
    best = search_result.candidates[0] if search_result and search_result.candidates else None
    best_avg = best.history_avg_90d if best else None
    best_price = best.lowest_price if best else 0
    lower_than_avg = round((best_avg - best_price) / best_avg, 4) if best_avg and best_price else None

    analysis = {
        "min_price": min(prices) if prices else None,
        "max_price": max(prices) if prices else None,
        "avg_price": int(sum(prices) / len(prices)) if prices else None,
        "avg_90d": int(sum(avg_90d_vals) / len(avg_90d_vals)) if avg_90d_vals else None,
        "lower_than_avg": lower_than_avg,
        "price_spread_pct": None,
        "match_score": round(
            len([p for p in (pref_result.items if pref_result else []) if p.matched]) / max(len(deals), 1), 2
        ),
        "within_budget": bool(decision and "符合心理价位" in decision.signals),
        "matched_preferences": list(set(pref_reasons)),
    }

    # query 摘要
    query_summary = None
    if intent and not intent.parse_failed:
        query_summary = {
            "raw_text": intent.raw_text,
            "normalized_text": intent.raw_text,   # SearchQueryDto 必填字段
            "origin_city": intent.origin.city if intent.origin else "",
            "origin_code": intent.origin.iata_code if intent.origin else "",
            "destination_city": intent.destination.city if intent.destination else "",
            "destination_code": intent.destination.iata_code if intent.destination else "",
            "date_start": intent.date_window.start_date if intent.date_window else "",
            "date_end": intent.date_window.end_date if intent.date_window else "",
            "budget": intent.budget_cny,
        }

    recommendation = {}
    if decision:
        recommendation = {
            "action": decision.action.value,
            "text": decision.text,
            "confidence": decision.confidence,
            "signals": decision.signals,
        }

    resp = FrontendResponse(
        user_id=state["request_user_id"],
        query=query_summary,
        deals=deals,
        analysis=analysis,
        recommendation=recommendation,
        meta={
            "generated_at": _now(),
            "source": "mock",
            "request_id": str(uuid.uuid4()),
            "result_count": len(deals),
            "fallback_mode": False,
        },
    )

    # 异步触发记忆写回（不阻塞响应）
    session_factory = state.get("_session_factory")
    if session_factory and intent and not intent.parse_failed:
        asyncio.create_task(_async_memory_writeback(
            user_id=state["request_user_id"],
            message=state["request_message"],
            intent=intent,
            session_factory=session_factory,
        ))

    return {**state, "response": resp}


async def _async_memory_writeback(user_id, message, intent, session_factory):
    try:
        from backend.services.memory_learner import learn_from_search, learn_from_query_history
        await learn_from_search(user_id, intent.model_dump(), session_factory)
        await learn_from_query_history(user_id, session_factory)
    except Exception:
        pass
```

---

### Step 2.9 新建 `backend/application/graph/factory.py`

```python
"""SearchGraph factory：构建并返回 compiled graph。"""
from __future__ import annotations
from langgraph.graph import StateGraph, END

from backend.application.graph.state import WorkflowState
from backend.application.graph.nodes.bootstrap_session import bootstrap_session_context
from backend.application.graph.nodes.parse_intent import parse_user_intent, route_after_intent
from backend.application.graph.nodes.clarify import clarify_response
from backend.application.graph.nodes.fetch_flights import run_flight_search
from backend.application.graph.nodes.match_preferences import run_preference_match
from backend.application.graph.nodes.judge_value import synthesize_decision
from backend.application.graph.nodes.render_response import render_response


def build_search_graph():
    g = StateGraph(WorkflowState)

    g.add_node("bootstrap_session_context", bootstrap_session_context)
    g.add_node("parse_user_intent",         parse_user_intent)
    g.add_node("clarify_response",          clarify_response)
    g.add_node("run_flight_search",         run_flight_search)
    g.add_node("run_preference_match",      run_preference_match)
    g.add_node("synthesize_decision",       synthesize_decision)
    g.add_node("render_response",           render_response)

    g.set_entry_point("bootstrap_session_context")
    g.add_edge("bootstrap_session_context", "parse_user_intent")
    g.add_conditional_edges(
        "parse_user_intent",
        route_after_intent,
        {"complete": "run_flight_search", "clarify": "clarify_response"},
    )
    g.add_edge("clarify_response",     END)
    g.add_edge("run_flight_search",    "run_preference_match")
    g.add_edge("run_preference_match", "synthesize_decision")
    g.add_edge("synthesize_decision",  "render_response")
    g.add_edge("render_response",      END)

    return g.compile()


# 模块级单例（main.py lifespan import 时编译一次）
search_graph = build_search_graph()
```

---

### Step 2.10 修改 `backend/api/search.py`

将 `/api/search` 完整替换为 graph runtime（**无 feature flag**）：

```python
"""POST /api/search — 主链路已切换到 application/graph runtime。"""
from __future__ import annotations
from fastapi import APIRouter, Request
from backend.schemas.search import SearchRequest, SearchResponseDto
from backend.application.graph.state import WorkflowState

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponseDto)
async def search_flights(payload: SearchRequest, request: Request) -> SearchResponseDto:
    from backend.application.graph.factory import search_graph

    initial: WorkflowState = {
        "request_user_id":    payload.user_id,
        "request_session_id": payload.session_id,
        "request_message":    payload.message,
        "context":            None,
        "clarify_count":      0,
        "intent":             None,
        "search_result":      None,
        "pref_result":        None,
        "decision":           None,
        "response":           None,
        "errors":             [],
        "_session_factory":   getattr(request.app.state, "session_factory", None),
        "_redis_client":      getattr(request.app.state, "redis_client", None),
    }

    final = await search_graph.ainvoke(
        initial,
        config={
            "run_name":       f"search:{payload.user_id}",
            "recursion_limit": 15,
        },
    )
    return SearchResponseDto.model_validate(final["response"].model_dump())
```

---

## Phase 3：验证与清理

### Step 3.1 新建 `backend/tests/graph/test_search_graph.py`

```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from backend.application.contracts.intent import (
    NormalizedIntent, LocationRef, DateWindow
)


def _base_state(**overrides):
    from backend.application.graph.state import WorkflowState
    base = dict(
        request_user_id="test", request_session_id=None,
        request_message="北京到三亚五一直飞",
        context=None, clarify_count=0, intent=None,
        search_result=None, pref_result=None,
        decision=None, response=None, errors=[],
        _session_factory=None, _redis_client=None,
    )
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_complete_intent_returns_deals():
    """完整意图 → run_flight_search → render_response → deals 非空。"""
    from backend.application.graph.factory import search_graph

    complete_intent = NormalizedIntent(
        origin=LocationRef(city="北京", iata_code="BJS"),
        destination=LocationRef(city="三亚", iata_code="SYX"),
        date_window=DateWindow(start_date="2026-05-01", end_date="2026-05-05"),
        parse_failed=False,
    )

    with patch("backend.application.graph.nodes.parse_intent._intent_chain") as mock:
        mock.ainvoke = AsyncMock(return_value=complete_intent)
        result = await search_graph.ainvoke(_base_state())

    assert result["response"] is not None
    assert len(result["response"].deals) > 0
    assert result["response"].recommendation.get("action") in ("buy_now", "watch", "skip")


@pytest.mark.asyncio
async def test_incomplete_intent_returns_clarify():
    """不完整意图 → clarify_response → deals=[]，含追问文本。"""
    from backend.application.graph.factory import search_graph

    incomplete = NormalizedIntent(
        destination=LocationRef(city="三亚", iata_code="SYX"),
        parse_failed=False,
    )

    with patch("backend.application.graph.nodes.parse_intent._intent_chain") as mock:
        mock.ainvoke = AsyncMock(return_value=incomplete)
        result = await search_graph.ainvoke(_base_state(request_message="我想去三亚"))

    assert result["response"].deals == []
    assert "请问" in result["response"].recommendation.get("text", "")


@pytest.mark.asyncio
async def test_parse_failed_returns_clarify():
    """解析失败 → 走 clarify 路径。"""
    from backend.application.graph.factory import search_graph

    with patch("backend.application.graph.nodes.parse_intent._intent_chain") as mock:
        mock.ainvoke = AsyncMock(return_value=NormalizedIntent(parse_failed=True))
        result = await search_graph.ainvoke(_base_state(request_message="随便"))

    assert result["response"].deals == []


@pytest.mark.asyncio
async def test_response_passes_searchresponsedto_validation():
    """端到端契约测试：FrontendResponse.model_dump() 能被 SearchResponseDto.model_validate() 接受。
    这是捕获 prices/query 字段名不对齐等 schema 问题的关键测试。
    """
    from backend.application.graph.factory import search_graph
    from backend.schemas.search import SearchResponseDto

    complete_intent = NormalizedIntent(
        origin=LocationRef(city="北京", iata_code="BJS"),
        destination=LocationRef(city="三亚", iata_code="SYX"),
        date_window=DateWindow(start_date="2026-05-01", end_date="2026-05-05"),
        parse_failed=False,
    )

    with patch("backend.application.graph.nodes.parse_intent._intent_chain") as mock:
        mock.ainvoke = AsyncMock(return_value=complete_intent)
        result = await search_graph.ainvoke(_base_state())

    assert result["response"] is not None
    # 不抛出 ValidationError 即通过
    dto = SearchResponseDto.model_validate(result["response"].model_dump())
    assert len(dto.deals) > 0
    assert dto.recommendation.action in ("buy_now", "watch", "skip")
```

```bash
pytest backend/tests/graph/test_search_graph.py -v
# 预期：4 个测试全部通过
```

---

### Step 3.2 旧路径对比验证

```bash
# 启动服务
uvicorn backend.main:app --reload --port 8000 &

# 用新 graph 发一条请求
curl -s -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","message":"北京到三亚五一直飞1200以内"}' \
  | python -m json.tool

# 关键验收点：
# ✅ deals 不为空
# ✅ recommendation.action 为 buy_now / watch
# ✅ recommendation.text ≤20字
# ✅ meta.fallback_mode = false
```

---

### Step 3.3 LangSmith Trace 验证（可选，需真实 key）

```bash
export LANGCHAIN_TRACING_V2=true
export LANGCHAIN_API_KEY=ls__your_key_here
export LANGCHAIN_PROJECT=faressniper-dev

curl -s -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"user_id":"e2e-test","message":"上海到东京下周末往返2000以内"}'

# 在 smith.langchain.com → faressniper-dev 验证：
# ✅ 1 条 Trace，名称 search:e2e-test
# ✅ 6 个 span：
#    bootstrap_session_context / parse_user_intent / run_flight_search /
#    run_preference_match / synthesize_decision / render_response
# ✅ parse_user_intent 和 synthesize_decision span 含 LLM token 用量
```

---

### Step 3.4 完整回归测试通过后删除旧文件

> **前提**：`pytest backend/tests/ -v` 全部通过，且 Step 3.2 对比结果与预期一致。

```bash
# 0. 先更新 main.py，移除已无用的 UnifiedLLMClient / SearchService 初始化
#    （否则删文件后 app 启动即崩溃）
#    修改内容：
#      - 删除 `from backend.llm.client import UnifiedLLMClient`
#      - 删除 `from backend.services.search_service import SearchService`
#      - 删除 lifespan 中 llm_client / search_service 的构造和 app.state 赋值
#      - app.state.session_factory / redis_client 保留（graph runtime 仍需要）

# 1. 全量 grep，确认 backend/ 所有模块都不再 import 待删文件
grep -rn "from backend.services.search_service\|from backend.services.intent_parser\
\|from backend.services.value_judge\|from backend.services.memory_learner\
\|from backend.llm.client\|from backend.llm.providers\
\|from backend.agents" backend/

# 1b. 同步检查 tests/ 目录下仍引用旧路径的测试文件（这些会让 grep 一直有结果）
#     已确认需要删除的旧测试（测对象已不存在，无迁移价值）：
#       backend/tests/test_orchestration_agent.py  → 引用 backend.agents.orchestration_agent
#       backend/tests/test_intention_agent.py      → 引用 backend.agents.intention_agent
#       backend/tests/test_skill_registry.py       → 引用 backend.agents.base
#       backend/tests/test_llm_providers.py        → 引用 backend.llm.client / providers
#
#     先删旧测试，再重跑 grep：
rm backend/tests/test_orchestration_agent.py
rm backend/tests/test_intention_agent.py
rm backend/tests/test_skill_registry.py
rm backend/tests/test_llm_providers.py

# 2. 上述 grep 零结果时，才执行删除
rm backend/services/search_service.py
rm backend/services/intent_parser.py
rm backend/services/value_judge.py
rm backend/services/memory_learner.py
rm -rf backend/agents/          # 原 0423 草稿目录，现已被 application/ 替代
rm backend/llm/client.py
rm backend/llm/providers.py

# 3. 保留（被 application/ 直接复用）
# backend/services/preference_matcher.py  ← nodes/match_preferences.py import
# backend/services/recommend_scorer.py   ← nodes/match_preferences.py import
# backend/services/holiday.py            ← nodes/match_preferences.py import
# backend/memory/long_term.py            ← context/assembler.py import
# backend/data_sources/mock_flights.py   ← nodes/fetch_flights.py import

# 4. 再次确认全部测试通过
pytest backend/tests/ -v
```

---

## 文件变更总览

### 新建（第一期）
```
backend/application/__init__.py
backend/application/contracts/__init__.py
backend/application/contracts/base.py
backend/application/contracts/workflow.py
backend/application/contracts/intent.py
backend/application/contracts/search.py
backend/application/contracts/preference.py
backend/application/contracts/decision.py
backend/application/context/__init__.py
backend/application/context/assembler.py
backend/application/graph/__init__.py
backend/application/graph/state.py
backend/application/graph/factory.py
backend/application/graph/nodes/__init__.py
backend/application/graph/nodes/bootstrap_session.py
backend/application/graph/nodes/parse_intent.py
backend/application/graph/nodes/clarify.py
backend/application/graph/nodes/fetch_flights.py
backend/application/graph/nodes/match_preferences.py
backend/application/graph/nodes/judge_value.py
backend/application/graph/nodes/render_response.py
backend/application/adapters/__init__.py         （占位，第二期填充）
backend/infrastructure/__init__.py
backend/infrastructure/llm/__init__.py
backend/infrastructure/llm/models.py
backend/tests/contracts/test_contracts.py
backend/tests/graph/test_search_graph.py
```

### 修改
```
backend/config.py               → 新增 LANGCHAIN_* 字段
backend/.env.example            → 新增 LangSmith 变量
backend/api/search.py           → 切换到 graph runtime（移除旧 SearchService 调用）
requirements.txt                → 新增 5 个依赖（langgraph>=0.3.0 等）
```

### 删除（Step 3.4，测试通过后执行）
```
backend/services/search_service.py
backend/services/intent_parser.py
backend/services/value_judge.py
backend/services/memory_learner.py
backend/agents/（整个目录，原草稿）
backend/llm/client.py
backend/llm/providers.py
```

### 保留不动（复用）
```
backend/services/preference_matcher.py
backend/services/recommend_scorer.py
backend/services/holiday.py
backend/memory/long_term.py
backend/data_sources/mock_flights.py
backend/utils/airport_codes.py
```

---

## 延后（第二期）

| 功能 | 来源 | 原因 |
|------|------|------|
| Langfuse prompt 监控 | 0414 阶段 7 | 需要 prompt 版本化体系，先跑通主链路再接 |
| Progressive skill loading | 0414 阶段 6 | FareSniper MVP 无 skill 选择逻辑 |
| Context budget 管理 | 0414 section 6.6 | 当前 token 消耗远未到天花板 |
| RecommendationGraph | 0414 | `/api/recommendations` 现有实现可用 |
| MemoryGraph | 0414 | 记忆写回**未删除**，仍在 `render_response.py` 通过 `asyncio.create_task(_async_memory_writeback)` 异步执行，只是不用 LangGraph 节点管理；延后是指不把写回改造成独立 graph 节点 |
| `run_memory_reasoning` 节点 | 0414 section 4.1 F3 | 当前记忆推理简单，无需独立 LLM 节点 |
| 并行 fan-out / join | 0414 section 4.2 | 等真实多平台爬虫接入后再引入 |

---

## 关键约束

| 约束 | 说明 |
|------|------|
| **目录** | 新代码只在 `backend/application/` 和 `backend/infrastructure/`，不再碰 `backend/agents/` |
| **契约优先** | 所有节点函数的输入输出必须是 `application/contracts/` 中声明的 Pydantic 模型，不接受 dict blob |
| **旧代码参考** | `preference_matcher.py`、`recommend_scorer.py`、`holiday.py` 等工程函数继续 import 复用，**不重写** |
| **安全删除** | Step 3.4 的删除必须在 grep 确认无依赖 + 测试全通过后执行 |
| **LangSmith** | 只需配置环境变量，LangGraph 自动 trace，不写自定义 instrumentation 代码 |
| **recursion_limit** | 通过 `graph.ainvoke(config={"recursion_limit": 15})` 控制，不放入 State |
