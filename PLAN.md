# FareSniper 项目计划（当前状态 2026-04-21）

## 一、现状快照

### 基础设施

| 服务 | 平台 | 状态 |
|------|------|------|
| PostgreSQL | Railway 内置 | ✅ 模型已定义，待 Step 7 云端部署 |
| Redis | Railway 内置 | ✅ 客户端已集成，待 Step 7 云端部署 |
| 前端部署 | Railway | ✅ Next.js 已配置 |
| 后端部署 | Railway | ✅ FastAPI 已配置，待 Step 7 部署 |

> 本地开发直连 Railway 云端 PostgreSQL + Redis，不需要本地 Docker。Railway 自动注入 `DATABASE_URL` 和 `REDIS_URL`。

---

### 代码完成情况

| 层 | 文件 | 状态 |
|----|------|------|
| **前端** | 全部 4 个页面 + api-client + types/api.ts | ✅ 已完成，不再改动 |
| **后端入口** | `main.py` + CORS + `config.py` | ✅ 已重构（lifespan 模式） |
| **DB 模型** | `db/models.py`（4张表）+ Alembic migration | ✅ 已完成 |
| **LLM 客户端** | `llm/client.py`（UnifiedLLMClient，OpenAI 兼容） | ✅ 已完成 |
| **Schemas** | `schemas/common.py`, `search.py`, `alerts.py` | ✅ 已对齐前端 DTO |
| **意图解析** | `services/intent_parser.py` | ✅ LLM + heuristic fallback |
| **偏好匹配** | `services/preference_matcher.py` | ✅ 纯工程逻辑，无 LLM |
| **价值判断** | `services/value_judge.py` | ✅ LLM + heuristic fallback |
| **搜索服务** | `services/search_service.py` | ✅ 3阶段 pipeline 重构完成 |
| **记忆学习** | `services/memory_learner.py` | ✅ 从搜索/点击异步学习 |
| **推荐服务** | `services/recommendation_service.py` | ✅ 冷启动 + 个性化卡片 |
| **长期记忆** | `memory/long_term.py` | ✅ PostgreSQL 持久化 |
| **假期服务** | `services/holiday.py` | ✅ 2026 年节假日 |
| **推荐评分** | `services/recommend_scorer.py` | ✅ PRD 7.1 公式 |
| **Mock 数据** | `data_sources/mock_flights.py` | ✅ 5条航线×3平台 |
| **API 路由** | `api/session.py`, `search.py`, `memory.py`, `recommendations.py`, `alerts.py` | ✅ 5 个 router |
| **爬虫基类** | `third_party/flights_monitor/base_scraper.py` | ✅ 已完成 |
| **携程爬虫** | `third_party/flights_monitor/ctrip_scraper.py` | ✅ BaseScraper 适配版 |
| **去哪儿爬虫** | `third_party/flights_monitor/qunar_scraper.py` | ✅ 已完成 |
| **同程爬虫** | `third_party/flights_monitor/tongcheng_scraper.py` | ✅ 已完成 |
| **飞猪爬虫** | `third_party/flights_monitor/fliggy_scraper.py` | ✅ 已完成 |
| **航旅纵横爬虫** | `third_party/flights_monitor/umetrip_scraper.py` | ✅ 已完成 |
| **多平台聚合** | `third_party/flights_monitor/multi_platform.py` | ✅ 已完成 |
| **测试** | `tests/` | ⚠️ 基础 conftest 存在，infra/完整业务测试待补 |

---

## 二、当前后端架构（已实现）

```
POST /api/search
    ↓
SearchService（3 阶段 pipeline）
    │
    ├── 1. IntentParser（LLM qwen-turbo + heuristic fallback）
    │       → NormalizedIntent（origin, dest, date, budget, constraints）
    │       → 最多 2 次澄清，超限后 Modal fallback
    │
    ├── 2. 并行：
    │       ├── fetch_flights（mock / ctrip_source）
    │       └── get_preferences（PostgreSQL）
    │
    ├── 3. PreferenceMatcher（纯工程）
    │       → 按 budget / airline / constraint 过滤 + boost
    │
    ├── 4. RecommendScorer（PRD 7.1 公式）
    │       → recommend_score = (hist×0.5 + pref×0.3 + bonus×0.2) × 10
    │
    ├── 5. ValueJudge（LLM qwen-plus + heuristic fallback）
    │       → verdict + signals（≤20字）
    │
    └── 6. 异步：learn_from_search + learn_from_query_history
```

**环境变量（新配置）：**
```
MODEL_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MODEL_API_KEY=<通义/DeepSeek/GLM 均可>
MODEL_INTENT=qwen-turbo     # IntentParser
MODEL_JUDGE=qwen-plus       # ValueJudge
```

---

## 三、API 接口契约（当前已实现）

| 方法 | 路径 | 用途 | 状态 |
|------|------|------|------|
| GET | `/health` | 健康检查 | ✅ |
| POST | `/api/session` | 分配 session_id（UUID） | ✅ |
| POST | `/api/search` | 自然语言搜索（带 session_id 多轮） | ✅ |
| GET | `/api/memory?user_id=` | 记忆页首屏 | ✅ |
| PATCH | `/api/memory` | 编辑/添加偏好 | ✅ |
| DELETE | `/api/memory/{field}?user_id=` | 删除偏好字段 | ✅ |
| GET | `/api/recommendations?user_id=` | 首页推荐卡 | ✅ |
| POST | `/api/alerts` | 创建价格提醒 | ✅ |
| GET | `/api/alerts?user_id=` | 查询价格提醒列表 | ✅ |

---

## 四、实施步骤

### ✅ 已完成

- [x] PRD 审查与修复（7 个问题点）
- [x] 后端整体重构（DB 模型、LLM 客户端、3 阶段 pipeline、5 个 router）
- [x] Alembic migration（prd_v11_refactor）
- [x] 多平台爬虫扩展（携程/去哪儿/同程/飞猪/航旅纵横 + 聚合器）

---

### Step 1：补全基础设施与业务测试 ⬅️ 当前优先级

#### 1.1 基础设施连通测试

**文件：`backend/tests/test_infra.py`**

```python
# Railway PostgreSQL：SELECT 1 成功
# Railway Redis：SET/GET 一个 key 成功
```

**conftest.py 需补充：**
```python
@pytest.fixture(scope="session")
async def db_engine():
    engine = create_async_engine(settings.database_url)
    yield engine
    await engine.dispose()

@pytest.fixture(scope="session")
async def redis_client():
    client = aioredis.from_url(settings.redis_url)
    yield client
    await client.aclose()
```

#### 1.2 核心业务逻辑测试

| 测试文件 | 覆盖内容 |
|----------|----------|
| `tests/test_intent_parser.py` | LLM 解析 + heuristic fallback；意图完整性判断 |
| `tests/test_preference_matcher.py` | budget/airline/constraint 过滤逻辑 |
| `tests/test_recommend_scorer.py` | PRD 7.1 公式验证 |
| `tests/test_value_judge.py` | heuristic fallback 输出格式 |
| `tests/test_search_service.py` | mock 完整 pipeline；澄清次数上限 |
| `tests/test_memory_learner.py` | learn_from_click 更新 budget/airline |
| `tests/test_db_models.py` | 4 张表 CRUD + rollback |

**验证命令：**
```bash
python -m pytest backend/tests/ -v
```

---

### Step 2：多平台爬虫接入真实数据源

> 当前爬虫代码结构完整，但 API 拦截点和响应字段需要真实运行后对齐。

**2.1 各平台响应字段验证（本地运行，有头模式）：**

```bash
cd backend/third_party/flights_monitor
python main.py monitor --from 北京 --multi-platform --test
```

对每个平台保存 `.debug_平台名_日期.json`，根据实际响应结构调整各 `parse_raw()` 中的字段路径。

**2.2 将多平台数据接入 SearchService：**

- 修改 `backend/data_sources/ctrip_source.py` → 重命名为 `flight_source.py`，调用 `multi_platform.search_multiplatform()`
- 输出格式与 `mock_flights.py` 对齐（含 `platform`、`booking_url` 字段）

**涉及文件：**
```
backend/data_sources/flight_source.py    （新建）
backend/services/search_service.py       （修改 fetch_flights 调用点）
backend/tests/test_flight_source.py      （新建，mock browser）
```

---

### Step 3：容错机制（Resilience）

**3.1 LLM 调用重试：**

```python
# backend/resilience/retry.py
async def retry_with_backoff(fn, max_retries=3, base_delay=1.0):
    ...
```

**3.2 爬虫降级：**

- 单平台超时 → 跳过该平台，继续其余平台
- 全部平台超时 → 返回 mock 数据（`ENABLE_MOCK_FALLBACK=true`）

**涉及文件：**
```
backend/resilience/__init__.py
backend/resilience/retry.py
backend/resilience/circuit_breaker.py    （可选）
backend/tests/test_resilience.py
```

---

### Step 4：Session 多轮对话优化

> 当前 session 只用 Redis 存储意图历史，多轮澄清上限 2 次。需要增强：

**4.1 ChatHistory 持久化（已有表结构，待接入）：**
- `POST /api/search` 自动把对话写入 `chat_history` 表
- 从 `GET /api/session/{session_id}/history` 恢复多轮上下文

**4.2 Session 过期处理：**
- TTL 30 分钟，过期后 `/api/search` 自动触发重新澄清

---

### Step 5：价格提醒后台任务

> `/api/alerts` 已实现创建和查询，还缺少实际触发逻辑。

**5.1 定时价格检查（异步 worker）：**

```python
# backend/workers/alert_checker.py
async def check_alerts():
    # 从 DB 取 status=active 的 alerts
    # 调用 flight_source 查最新价格
    # 若 current_price <= target_price → 更新 status=triggered + 发通知
```

**选项：**
- Railway Cron Job（推荐，每小时）
- APScheduler 内嵌到 FastAPI lifespan

---

### Step 6：PRD 对齐补全

| PRD 章节 | 功能 | 状态 |
|----------|------|------|
| PRD 5.1 聊天输入 | 多轮澄清（最多2次） | ✅ |
| PRD 5.2 搜索结果页 | DealCard 列表 + 分析 + 建议 | ✅ |
| PRD 5.3 首页推荐 | 冷启动 + 个性化卡片 | ✅ |
| PRD 5.4 记忆页 | 偏好展示/编辑/删除 | ✅ |
| PRD 6 LLM Pipeline | IntentParser + ValueJudge | ✅ |
| PRD 7 推荐算法 | recommend_score 公式 | ✅ |
| PRD 8 推荐卡片 | 8张卡片，多出发城市 | ✅ |
| PRD 9 个人页 | 静态占位（MVP） | ✅ |
| 价格提醒 | 创建/查询 API | ✅ 接口已实现，worker 待 Step 5 |
| 历史均价 | hist_avg_90d 字段 | ✅ mock 数据已含，真实数据待 Step 2 |
| h5_fallback_url | booking_url fallback | ✅ mock 数据已含 |

---

### Step 7：云端部署（Railway）

**Railway 画布操作：**
1. `railway.app` → 新建 Project → 连接 GitHub repo
2. 画布 Add Service → Database → **PostgreSQL**（自动生成 `DATABASE_URL`）
3. 画布 Add Service → Database → **Redis**（自动生成 `REDIS_URL`）
4. 画布 Add Service → GitHub Repo → 选 `backend/` 目录
5. 将 PostgreSQL、Redis 变量关联到后端 Service（画布连线）
6. 填写环境变量（`MODEL_API_KEY`、`MODEL_BASE_URL` 等）

**前端：**
1. 画布 Add Service → GitHub Repo → 选 `frontend/` 目录（Next.js 自动识别）
2. 注入：`NEXT_PUBLIC_API_URL` = Railway backend 域名

**验证：**
```bash
# 健康检查
curl https://your-backend.railway.app/health

# 端到端测试
cd backend && pytest tests/test_e2e.py -v
```

---

## 五、文件变更总览（当前实际状态）

### 本轮重构新建/重写（已完成）
```
backend/db/models.py                              ✅ 重写
backend/db/migrations/versions/a1b2c3d4e5f6_*.py ✅ 新建
backend/config.py                                 ✅ 重写
backend/main.py                                   ✅ 重写
backend/schemas/common.py                         ✅ 重写
backend/schemas/search.py                         ✅ 重写
backend/schemas/alerts.py                         ✅ 新建
backend/api/session.py                            ✅ 新建
backend/api/search.py                             ✅ 重写
backend/api/memory.py                             ✅ 重写
backend/api/recommendations.py                    ✅ 重写
backend/api/alerts.py                             ✅ 新建
backend/llm/client.py                             ✅ 重写
backend/services/intent_parser.py                 ✅ 新建
backend/services/preference_matcher.py            ✅ 新建
backend/services/value_judge.py                   ✅ 新建
backend/services/recommend_scorer.py              ✅ 新建
backend/services/search_service.py               ✅ 重写
backend/services/recommendation_service.py       ✅ 重写
backend/services/memory_learner.py               ✅ 新建
backend/services/holiday.py                      ✅ 新建
backend/memory/long_term.py                      ✅ 更新
backend/data_sources/mock_flights.py             ✅ 新建
backend/third_party/flights_monitor/base_scraper.py    ✅ 新建
backend/third_party/flights_monitor/ctrip_scraper.py   ✅ 新建
backend/third_party/flights_monitor/qunar_scraper.py   ✅ 新建
backend/third_party/flights_monitor/tongcheng_scraper.py ✅ 新建
backend/third_party/flights_monitor/fliggy_scraper.py  ✅ 新建
backend/third_party/flights_monitor/umetrip_scraper.py ✅ 新建
backend/third_party/flights_monitor/multi_platform.py  ✅ 新建
```

### 待完成
```
backend/tests/test_infra.py                  ❌ Step 1
backend/tests/test_intent_parser.py          ❌ Step 1
backend/tests/test_search_service.py         ❌ Step 1
backend/data_sources/flight_source.py        ❌ Step 2
backend/resilience/retry.py                  ❌ Step 3
backend/workers/alert_checker.py             ❌ Step 5
```

### 始终保留不动
```
frontend/**                    — 前端代码完全不动
backend/tools/*.py             — 4 个纯函数工具
backend/data_sources/base.py   — DataSource 抽象基类
third_party/flights_monitor/ctrip_api.py   — 原版携程爬虫，保留向后兼容
```

---

## 六、架构演进路径

| 阶段 | 升级内容 | 状态 |
|------|----------|------|
| v1.1 | 真实航班数据（多平台 Step 2） | 爬虫字段验证完成后启动 |
| v1.2 | 价格提醒 worker（Step 5） | 用户有订阅需求后启动 |
| **v2.0** | **LangGraph + LangChain + LangSmith 全量重构（见第八节）** | **⬅️ 当前规划中** |
| v2.1 | LangSmith 自定义评估器 + 告警 | v2.0 上线后 |
| v3.0 | 流式 SSE 响应 | 搜索延迟 P95 > 5s |

---

## 七、最终验证清单

```bash
# 单元测试（全部通过）
python -m pytest backend/tests/ -v

# 本地联调（直连 Railway 云端 PG+Redis）
cd backend && uvicorn backend.main:app --reload
cd frontend && npm run dev

# 多平台爬虫测试（有头模式）
cd backend/third_party/flights_monitor
python main.py monitor --from 北京 --test

# 多平台爬虫（聚合模式）
python main.py monitor --from 北京 --multi-platform --test
```

---

## 八、v2.0：LangGraph + LangChain + LangSmith 全量重构方案

> **动机**：当前手工服务层编排（SearchService / RecommendationService / MemoryLearner）无法观测完整调用链，条件分支散落在 service 方法内，LLM 节点与工程节点耦合，异步记忆学习难以追踪。
>
> **目标**：用 LangGraph StateGraph 替换手工编排，LangChain ChatModel 替换 UnifiedLLMClient，LangSmith 为每次请求生成完整 Trace。

---

### 8.1 当前后端函数调用图

```
POST /api/search
└── SearchService.search(user_id, message, session_id)
    ├── _load_session_history()                # DB: 读取最近10条聊天
    ├── IntentParser.parse()
    │   ├── _parse_via_llm()                   # UnifiedLLMClient → Qwen/DeepSeek
    │   └── _parse_heuristic()                 # fallback: 正则提取城市/日期/预算
    ├── is_intent_complete()                   # 条件分支
    │   └── (缺失) → _clarify_response()       # 返回澄清提示
    ├── [并行]
    │   ├── _fetch_flights()                   # Mock 或 CtripSource.search_flights()
    │   └── _get_preferences()                 # DB: user_preferences
    ├── run_preference_match()                 # 纯工程: budget/airline/constraint
    ├── is_holiday()                           # 硬编码节假日列表
    ├── sort_deals() → calc_recommend_score()  # 评分+排序
    ├── ValueJudge.judge()
    │   ├── _judge_via_llm()                   # UnifiedLLMClient
    │   └── _judge_heuristic()                 # fallback
    ├── [异步非阻塞]
    │   ├── learn_from_search()                # DB: query_history
    │   └── learn_from_query_history()         # DB: 推断 user_preferences
    └── return SearchResponseDto

GET /api/recommendations
└── RecommendationService.get_cards(user_id)
    ├── LongTermMemory.get_preferences()
    ├── (冷启动) → _build_cold_start_cards()   # 8条热门航线
    └── (有偏好) → _build_personalized_cards() # frequent_cities + budget

MemoryLearner [background]:
├── learn_from_search()     → DB: add_query()
├── learn_from_click()      → DB: add_click() + upsert_preferences()
└── learn_from_query_history() → DB: upsert_preferences()
```

---

### 8.2 目标架构：LangGraph 节点拓扑

#### SearchGraph（主链路）

```
[START]
  │
  ▼
┌───────────────┐
│ load_context  │  读 session 历史 + user_id 注入 State
└───────┬───────┘
        ▼
┌───────────────┐
│ parse_intent  │  ChatPromptTemplate → ChatModel → StructuredOutputParser
└───────┬───────┘
        ▼
┌──────────────────────┐         ┌────────────────────┐
│ check_intent_complete│──NO──▶  │  clarify_response  │──▶ [END]
└──────────┬───────────┘         └────────────────────┘
           │ YES
           ▼
┌──────────────────────────────────────────┐
│  fetch_context (并行)                    │
│   ├─ fetch_flights()   → Mock/Ctrip      │
│   └─ fetch_preferences() → DB            │
└──────────────────┬───────────────────────┘
                   ▼
┌───────────────────────┐
│  match_preferences    │  纯工程规则（无 LLM）
└──────────┬────────────┘
           ▼
┌───────────────────────┐
│  score_and_sort       │  calc_recommend_score + sort_deals
└──────────┬────────────┘
           ▼
┌───────────────────────┐
│  judge_value          │  ChatModel → StructuredOutputParser (signals + advice)
└──────────┬────────────┘
           ▼
┌───────────────────────┐
│  build_response       │  组装 SearchResponseDto
└──────────┬────────────┘
           ├──▶ [异步触发 MemoryGraph]
           ▼
         [END]
```

**SearchState TypedDict：**
```python
from __future__ import annotations
from typing_extensions import TypedDict

class SearchState(TypedDict):
    user_id: str
    session_id: str | None
    message: str
    # plain list：每次 invoke 全新状态，load_context 从 DB 一次性加载，不需要 Annotated reducer
    session_history: list[dict]
    intent: dict | None
    intent_complete: bool            # conditional edge 读取，决定路由方向
    clarify_count: int
    fallback_triggered: bool         # 任意节点触发降级时置 True
    flights: list[dict]
    preferences: dict | None
    matched_flights: list[dict]
    sorted_deals: list[dict]
    value_judgment: dict | None
    response: dict | None
    error: str | None
```

> `trace_id` 由 LangSmith 自动生成，不进 State；防死循环改用 `graph.invoke(config={"recursion_limit": 15})`。
>
> **注**：`session_history` 不使用 `Annotated` reducer。`Annotated[list, operator.add]` 适用于有 checkpointer 跨 invoke 累积的场景；本项目每次请求都是全新 invocation，所有节点采用 `{**state, "key": value}` 返回模式，使用 Annotated reducer 会导致每个节点执行一次 history 就翻倍。

#### RecommendationGraph

```
[START] → fetch_preferences → check_cold_start
                                   ├─YES─▶ build_cold_start_cards ──▶ [END]
                                   └─NO──▶ build_personalized_cards ─▶ [END]
```

**RecommendationState TypedDict：**
```python
class RecommendationState(TypedDict):
    user_id: str
    preferences: dict | None   # 从 DB 加载的用户偏好
    is_cold_start: bool        # check_cold_start 节点写入，路由用
    cards: list[dict]          # 最终卡片列表（4-8 张）
```

#### MemoryGraph（异步子图）

```
[START] → record_query → infer_preferences → update_preferences → [END]
```

**MemoryState TypedDict：**
```python
class MemoryState(TypedDict):
    user_id: str
    query_text: str            # 本次搜索的原始文本
    flights_returned: list[dict]  # 返回给用户的航班列表，供推断偏好
    click_event: dict | None   # 用户点击事件（learn_from_click 路径）
```

---

### 8.3 LangSmith 集成

**环境变量：**
```bash
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=<your-key>
LANGCHAIN_PROJECT=faressniper-prod   # 或 faressniper-dev
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
```

**Trace 粒度：**
- 每次 `POST /api/search` → 一条 Trace，`run_name="search:{user_id}"`
- 内含 spans：`load_context` / `parse_intent` / `fetch_context` / `match_preferences` / `score_and_sort` / `judge_value` / `build_response`
- LLM 节点自动产生 LLM span（含 token 用量）
- 自定义 metadata：`{"user_id", "session_id", "intent_origin", "intent_dest"}`
- LangGraph 原生支持，设置环境变量后自动激活，无需手动 `@traceable`

---

### 8.4 LangChain ChatModel 替换

| 原实现 | 新实现 |
|--------|--------|
| `UnifiedLLMClient` → Qwen | `ChatTongyi(model="qwen-max")` |
| `UnifiedLLMClient` → DeepSeek | `ChatOpenAI(base_url="https://api.deepseek.com", model="deepseek-chat")` |
| Mock LLM | `FakeListChatModel(responses=[...])` |
| 手工 JSON 解析 | `.with_structured_output(IntentSchema)` |
| 手工 Prompt 字符串 | `ChatPromptTemplate.from_messages([...])` |

**IntentParser → LangChain Chain：**
```python
intent_chain = (
    ChatPromptTemplate.from_messages([
        ("system", INTENT_SYSTEM_PROMPT),
        MessagesPlaceholder("history"),
        ("human", "{message}"),
    ])
    | ChatTongyi(model=config.MODEL_INTENT).with_structured_output(IntentSchema)
)
```

---

### 8.5 迁移路径（5 个 Phase）

| Phase | 内容 | 时间 |
|-------|------|------|
| **P1 基础设施** | 安装依赖；新建 `backend/agents/`；`langchain_models.py`；`.env` 添加 LangSmith 变量 | 1-2天 |
| **P2 SearchGraph** | `state.py` + `nodes/` 所有节点 + `search_graph.py`；改写 `api/search.py` | 2-3天 |
| **P3 RecommendationGraph** | `recommendation_graph.py`；改写 `api/recommendations.py` | 1天 |
| **P4 MemoryGraph** | `memory_graph.py`；在 `build_response` 末尾异步触发 | 1天 |
| **P5 清理验证** | 删旧 services/llm；LangSmith 控制台验证；回归测试 | 1天 |

---

### 8.6 文件清单

**新建：**
```
backend/agents/__init__.py
backend/agents/state.py                    # TypedDict state 定义
backend/agents/search_graph.py             # SearchGraph StateGraph
backend/agents/recommendation_graph.py    # RecommendationGraph
backend/agents/memory_graph.py             # MemoryGraph (async)
backend/agents/nodes/context.py            # load_context
backend/agents/nodes/intent.py             # parse_intent
backend/agents/nodes/flights.py            # fetch_flights + fetch_preferences
backend/agents/nodes/matching.py           # match_preferences + score_and_sort
backend/agents/nodes/value.py              # judge_value
backend/agents/nodes/response.py           # build_response + clarify_response
backend/agents/nodes/memory.py             # record_query + infer_prefs + update_prefs
backend/llm/langchain_models.py            # ChatTongyi / ChatOpenAI / FakeLLM
```

**修改：**
```
backend/api/search.py                      # 调用 search_graph.ainvoke()
backend/api/recommendations.py             # 调用 recommendation_graph.ainvoke()
backend/config.py                          # 新增 LANGCHAIN_* 字段
backend/.env.example                       # 新增 LangSmith 变量
backend/main.py                            # 启动时 compile graphs
requirements.txt                           # 新增依赖
```

**删除（Phase 5）：**
```
backend/services/search_service.py         → 迁移到 search_graph + nodes/
backend/services/recommendation_service.py → 迁移到 recommendation_graph
backend/services/memory_learner.py         → 迁移到 memory_graph
backend/services/intent_parser.py          → nodes/intent.py
backend/services/value_judge.py            → nodes/value.py
backend/services/preference_matcher.py     → nodes/matching.py
backend/services/recommend_scorer.py       → nodes/matching.py
backend/llm/client.py                      → langchain_models.py
backend/llm/providers.py                   → 合并到 langchain_models.py
```

---

### 8.7 新增依赖

```toml
langgraph = ">=0.3.0"
langchain = ">=0.3.0"
langchain-community = ">=0.3.0"
langsmith = ">=0.1.0"
langchain-openai = ">=0.2.0"
```

---

### 8.8 验证方案

```bash
# 单节点独立测试
python -c "from backend.agents.nodes.intent import parse_intent; ..."

# Graph 集成测试（FakeListChatModel mock LLM）
pytest backend/tests/test_search_graph.py -v

# LangSmith Trace 验证（faressniper-dev 项目下检查 7 个 span）
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test","message":"北京到三亚五一直飞1200以内"}'

# API 回归（响应结构与重构前一致）
pytest backend/tests/test_e2e.py -v
```
