# 特价机票发现平台 PRD

## 1. 基本信息

| 项目 | 说明 |
|------|------|
| 功能名称 | 特价机票发现平台 |
| 所属模块 | 全产品 |
| 版本号 | v2.0 |
| 负责人 | [待填] |
| 预计上线时间 | [待填] |

## 2. 更新记录

| 时间 | 作者 | 更新说明 |
|------|------|----------|
| 2026-04-11 | | 初稿 |
| 2026-04-17 | | 按 prd-writer 规范重写，补全 Agent State、Prompt 设计、字段定义 |
| 2026-04-18 | | 补全 API 接口规范（5个接口）、完整 DTO 定义、前端页面数据流（4个页面）|
| 2026-04-18 | | 补充 user_id 生命周期、session 多轮对话、价格监控 MVP、recommend_score 计算规则、deals 排序规则、统一新用户阈值，记忆存储改为纯后端 DB |
| 2026-04-19 | | 确认所有待定决策：booking_url 深链规则、节假日写死规则、追问降级 Modal 浮层、PreferenceMatch 改纯工程规则、模型改环境变量配置支持国内模型 |
| 2026-05-05 | | 按完整产品 PRD 规范（prd-writer v2 skill）升级至 v2.0：补充竞品分析、北极星指标体系、产品系统架构、MVP 假设清单、0-1 商业模式、AI 评估体系、模型选型 |
| 2026-05-06 | | 更新比价技能：工程爬虫每 1 小时入库，用户查询读数据库缓存；补充偏好来源在 MemoryPage 的展示规则 |

---

## 3. 业务背景及目标

### 3.1 行业背景与核心痛点

**市场现状**：国内机票在线预订年交易额超 3000 亿元，但价格比较行为极其分散——用户平均需在携程、去哪儿、飞猪、航司官网、转机工具之间切换 5+ 次，单次查票耗时 30-60 分钟。

**核心痛点（5人用户访谈验证）**：

| 痛点 | 场景描述 | 严重程度 |
|------|---------|---------|
| 多平台切换效率低 | 同一航线各平台价差高达 15%，但逐一比对耗时巨大 | 高 |
| 缺乏客观判断标准 | 买完票仍不确定「这是不是真的便宜」 | 高 |
| 低频出行者无偏好积累 | 每次都从零开始，不知道自己偏好什么价位/航司 | 中 |
| 价格波动焦虑 | 今天看了明天涨价，不知道该不该等 | 中 |

**Jobs-to-be-done 视角**：

> 「当我需要买机票时，我想用最短时间确认当前这张票值不值得买，而不是在各平台反复对比后仍感到不确定。」

**目标用户**：18-30 岁价格敏感出行者，学生 / 应届毕业生 / 背包客为主，出行频率 1-5 次/年，习惯多平台比价，愿意为省 100 元货比三家。

**产品介绍**：对话式入口聚合多平台机票价格，结合用户偏好记忆输出「值得买」判断，让用户在一个界面完成查票→决策→跳转购买的完整闭环。

### 3.2 北极星指标与核心 KPI

**北极星指标**：查询后跳转购买次数（Query-to-Purchase Clicks，简称 QPC）

选择理由：QPC 同时衡量产品对用户的价值（查到了满意的票）和对商业的价值（产生了跳转转化），是两者的交集。

| 层级 | 指标 | 当前值 | MVP 目标 | v1.1 目标 |
|------|------|--------|---------|---------|
| 北极星指标 | 月 Query-to-Purchase Clicks | 0（未上线） | 500 次/月 | 2000 次/月 |
| 转化漏斗 | 查询→结果展示率 | — | > 80% | > 90% |
| 转化漏斗 | 结果→跳转购买率 | — | > 25% | > 35% |
| 用户价值 | AI 建议采纳率 | — | > 30% | > 40% |
| 效率 | 单次决策时间 | 30-60 min | < 5 min | < 3 min |
| 留存 | 7 日留存率 | — | > 15% | > 25% |
| 体验 | 意图解析成功率 | — | > 90% | > 93% |

**护栏指标（不能被牺牲的底线）**：

- 跳转深链跳转失败率 < 5%（否则损害用户信任）
- AI 建议误导率 < 3%（「建议买」但实际价格高于历史均价的比例）
- 页面 P95 加载时间 < 3s

---

## 4. 竞品分析

### 4.1 竞品概览

| 竞品 | 核心能力 | 目标用户 | 商业模式 | 优势 | 劣势 |
|------|---------|---------|---------|------|------|
| **携程** | 全平台预订 + 售后服务 | 全年龄商旅/休闲 | 佣金 + 服务费 | 一站式完成，品牌信任度高，服务有保障 | 界面复杂，价格未必最优，无「值不值得买」判断 |
| **去哪儿** | 比价聚合 + 低价票 | 价格敏感用户 | 佣金分成 | 比价直观，低价票源多 | 跳转体验差（到第三方购买），无 AI 判断，无偏好学习 |
| **Google Flights** | 价格预测 + 日历视图 | 有行程灵活性的用户 | 导流（无直接变现） | 日历视图强，价格趋势预测好，界面简洁 | 不聚合国内平台，无中文深度优化，无法直接购票 |
| **Hopper** | 价格预测 + 最佳购买时机通知 | 年轻价格敏感用户 | 订阅制会员 + 佣金 | 价格预测准确（AI 驱动），通知体验好，等待/立买判断明确 | 国内航线覆盖极差，英文界面 |
| **航班管家** | 航班动态追踪 + 比价 | 商旅常客 | 广告 + 增值服务费 | 航班实时追踪是核心优势，商旅功能完善 | 比价功能弱，无 AI「值得买」建议，界面信息密度过高 |

### 4.2 差异化定位

**一句话定位**：FareSniper 是唯一把「多平台聚合比价」+「AI 值得买判断」+「用户偏好记忆」三者合一的中文机票决策助手。

**三个核心差异点（可验证）**：

1. **对话式入口降低查询门槛**：竞品均为表单/日历式输入，FareSniper 支持「五一去三亚，预算600」这样的自然语言，适合低频出行者（1-5次/年）的使用习惯
2. **个性化「值得买」判断**：去哪儿/携程只展示价格，不给决策建议；Hopper 只有通用预测，不结合用户个人偏好；FareSniper 结合用户历史心理价位 + 历史均价给出定制化建议
3. **偏好自动学习**：每次查询/点击后静默更新用户画像，下次推荐精准度提升，形成使用飞轮

**定位矩阵**（两个关键维度）：

```
            高 AI 决策建议
                │
    FareSniper  │   Hopper
                │
────────────────┼────────────────
 聚合多平台     │          单一来源
                │
    去哪儿      │  航班管家/携程
                │
            低 AI 决策建议
```

---

## 5. 产品方案

### 5.1 产品定义

**一句话描述**：价格敏感的 18-30 岁年轻出行者用 FareSniper 来在一个对话界面完成「多平台比价 + AI 值得买判断」，与去哪儿等比价平台不同的是，FareSniper 能记住用户偏好并给出个性化的买/不买建议。

**核心用户旅程**：

```
触发需求（准备出行）
    ↓
打开 FareSniper，输入自然语言（如「五一去三亚，预算600」）
    ↓
AI 解析意图（< 1s），必要时追问缺失信息
    ↓
读取数据库中的航班价格缓存，返回最近一次成功爬取结果
    ↓
展示结果卡片 + AI「值得买」信号 + 一句话建议
    ↓
用户点击跳转至最低价平台完成购票
    ↓（异步）
系统记录行为，更新偏好画像（下次更精准）
```

### 5.2 系统架构

#### 5.2.1 整体分层架构

```
┌─────────────────────────────────────────────────────────────┐
│                      前端层（Vercel）                        │
│  Next.js App Router · 4 Pages · lib/api.ts · lib/mappers.ts │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS REST（JSON）
┌──────────────────────────▼──────────────────────────────────┐
│                     API 层（FastAPI）                        │
│  /api/session  /api/search  /api/memory                      │
│  /api/recommendations  /api/alerts                           │
│  CORS Middleware · Lifespan 管理基础设施启动/关闭             │
└──────────────┬────────────────────────┬─────────────────────┘
               │                        │
┌──────────────▼──────────┐  ┌──────────▼──────────────────┐
│   Application 层         │  │   Services 层               │
│   LangGraph SearchGraph  │  │   RecommendationService     │
│   7 个 Graph 节点        │  │   MemoryLearner（异步）      │
│   WorkflowState          │  │   RecommendScorer           │
│   ContextAssembler       │  │   HolidayService            │
└──────────────┬──────────┘  └──────────┬────────────────────┘
               │                        │
┌──────────────▼────────────────────────▼─────────────────────┐
│                    基础设施层                                 │
│  ┌────────────────┐  ┌──────────────┐  ┌─────────────────┐  │
│  │  PostgreSQL    │  │  Redis       │  │  LLM Service    │  │
│  │  (SQLAlchemy   │  │  (aioredis)  │  │  (Dashscope /   │  │
│  │   async)       │  │  Session缓存 │  │   DeepSeek)     │  │
│  │  11张目标表    │  │  TTL 30min   │  │  qwen-plus      │  │
│  └────────────────┘  └──────────────┘  │  function call  │  │
│                                        └─────────────────┘  │
│  ┌────────────────┐  ┌──────────────┐                       │
│  │  CircuitBreaker│  │  LangSmith   │                       │
│  │  + Retry       │  │  Tracing     │                       │
│  │  (per platform)│  │  (run_id)    │                       │
│  └────────────────┘  └──────────────┘                       │
└─────────────────────────────────────────────────────────────┘
```

#### 5.2.2 LangGraph 搜索工作流（SearchGraph）

后端核心是一个基于 **ReAct（Reasoning + Acting）** 模式的 LangGraph `StateGraph`，代码入口在 `backend/application/graph/factory.py`。图由两个节点构成循环：**ReAct 代理节点**负责推理和工具调用决策，**工具执行节点**负责执行具体工具并返回结果。

**ReAct 模式与原线性 DAG 的核心差异：**

| 维度 | 原线性 DAG | ReAct 循环 |
|------|-----------|-----------|
| 流程控制 | 代码预定义条件边（if 信息完整 → 搜索） | LLM 自主推理决定调用哪个工具 |
| 追问触发 | 固定节点，LLM 主观判断"够不够" | `ask_user` 工具调用，由槽位校验结果驱动 |
| 多轮槽位 | 每轮重新解析，无跨轮累积 | `accumulated_slots` 跨轮合并，已填槽无需重复询问 |
| 扩展新意图 | 需修改图结构和路由条件 | 只需新增工具定义 |

**节点流转图：**

```
初始化会话上下文（bootstrap）
        │
        ▼
┌─────────────────────────┐
│   ReAct 代理节点         │ ◄─────────────────┐
│  （LLM 推理 + 工具选择）  │                   │
└─────────┬───────────────┘                   │
          │                                   │
     有工具调用？                               │
          │ Yes                               │
          ▼                                   │
┌─────────────────────────┐                   │
│   工具执行节点            │                   │
│  ├── ask_user           │                   │
│  ├── search_flights     │ ──── 结果注入消息 ──┘
│  ├── get_preferences    │
│  └── judge_value        │
└─────────────────────────┘
          │ No（LLM 无更多工具调用，直接输出最终回复）
          ▼
         END
```

**各节点职责：**

| 中文说明 | 节点函数名 | 文件 | 类型 | 职责 |
|---------|------|------|------|------|
| 初始化会话上下文 | `bootstrap_session_context` | `nodes/bootstrap_session.py` | 工程 | 加载 session 历史消息，从 Redis 恢复 `accumulated_slots`；从 Redis 加载意图注册表（TTL 60s，miss 时查 DB）并动态构建 tool schema；注入用户偏好快照，构造初始 `HumanMessage` |
| ReAct 代理 | `react_agent` | `nodes/react_agent.py` | LLM | 绑定全部工具的 LLM（qwen-plus 或 qwen-max），读取 `messages` 历史推理，输出工具调用或最终文本回复 |
| 工具执行 | `tool_executor` | `nodes/tool_executor.py` | 工程 | 执行代理选择的工具，结果以 `ToolMessage` 写回 `messages`；`ask_user` 调用时同步保存 `accumulated_slots` 到 Redis |

**路由逻辑（`route_after_agent`）：**

```python
def route_after_agent(state: WorkflowState) -> str:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tool_executor"   # 有工具调用 → 执行工具
    return END                   # 无工具调用 → LLM 已生成最终回复
```

**WorkflowState 核心字段（`application/graph/state.py`）：**

```python
from langgraph.graph.message import add_messages

class WorkflowState(TypedDict):
    # ReAct 核心：消息列表，由 add_messages 操作自动追加（不覆盖）
    messages: Annotated[list[BaseMessage], add_messages]

    # 用户标识
    request_user_id: str
    request_session_id: str | None

    # 跨轮槽位累积（从 Redis 加载，ask_user 时持久化）
    accumulated_slots: SlotBundle | None

    # 追问控制
    clarify_count: int        # ask_user 被调用次数，≥2 时代理改用降级工具
    fallback_triggered: bool

    # 工具执行后填充的结构化结果（供 judge_value 工具读取）
    search_result: FlightSearchResult | None
    pref_result: PreferenceMatchResult | None
    decision: DecisionResult | None

    # 最终写回前端的响应（由代理最后一条 AIMessage 或 render_response 填充）
    response: FrontendResponse | None
    errors: list[WorkflowError]
```

`recursion_limit=20` 通过 `graph.invoke(config={"recursion_limit": 20})` 传入，防止工具调用死循环。

#### 5.2.3 后端模块结构

```
backend/
├── api/                  # FastAPI 路由层（5个 router）
│   ├── search.py         # POST /api/search → 调用 SearchGraph
│   ├── session.py        # POST /api/session
│   ├── memory.py         # GET/PATCH/DELETE /api/memory
│   ├── recommendations.py# GET /api/recommendations
│   └── alerts.py         # GET/POST /api/alerts
│
├── application/
│   ├── graph/            # LangGraph 工作流
│   │   ├── factory.py    # build_search_graph()，编译图
│   │   ├── state.py      # WorkflowState TypedDict
│   │   └── nodes/        # 7个节点实现
│   └── contracts/        # 节点间传递的强类型数据契约
│       ├── intent.py     # NormalizedIntent
│       ├── search.py     # FlightSearchResult
│       ├── preference.py # PreferenceMatchResult
│       └── decision.py   # DecisionResult / FrontendResponse
│
├── services/             # 业务逻辑（无 HTTP 依赖）
│   ├── intent_parser.py  # LLM 调用封装 + JSON 解析兜底
│   ├── value_judge.py    # LLM 调用封装 + signals 生成
│   ├── preference_matcher.py  # 纯工程规则偏好匹配
│   ├── recommend_scorer.py    # recommend_score 0-10 分计算
│   ├── memory_learner.py      # 异步偏好学习（行为推断）
│   ├── holiday.py             # is_holiday() 工程规则
│   └── recommendation_service.py  # 个性化推荐卡片生成
│
├── data_sources/         # 查价数据源抽象层
│   ├── base.py           # 抽象基类 DataSource
│   ├── ctrip_source.py   # 携程数据源适配
│   ├── flight_cache_repository.py # 查询链路读取数据库缓存
│   └── registry.py       # 数据源注册表
│
├── jobs/                 # 后台任务
│   ├── flight_crawl_scheduler.py  # 每 1 小时生成爬取任务
│   └── flight_crawl_worker.py     # 调用 flights_monitor 并写入快照表
│
├── db/
│   ├── models.py         # SQLAlchemy ORM 表（见 5.2.5）
│   └── session.py        # async_sessionmaker 工厂
│
├── resilience/
│   ├── circuit_breaker.py  # 三态熔断器（CLOSED/OPEN/HALF_OPEN）
│   └── retry.py            # 指数退避重试装饰器
│
└── infrastructure/llm/   # LLM 客户端封装
    └── models.py         # OpenAI-compatible client（支持 Dashscope/DeepSeek）
```

#### 5.2.4 前端架构（Next.js App Router）

```
frontend/
├── app/
│   ├── layout.tsx          # 全局 Shell，底部 Tab 导航
│   └── page.tsx            # 入口，渲染 AppShell
│
├── components/
│   ├── app-shell.tsx       # Tab 切换路由（chat/explore/memory/personal）
│   ├── chat-page.tsx       # 主查票页：对话流 + 结果卡片
│   ├── explore-page.tsx    # 探索发现：推荐瀑布流 + 盲盒
│   ├── memory-page.tsx     # 记忆空间：日记式偏好展示
│   ├── personal-page.tsx   # 个人中心：关系图 + 监控列表
│   └── discovery-card-content.tsx  # 共用航班结果卡片组件
│
├── lib/
│   ├── api.ts              # 所有后端接口调用（fetch 封装）
│   └── mappers.ts          # DealCardDto → DiscoveryCardContent props 映射
│
└── app/api/
    └── recommended-questions/route.ts  # Next.js API Route（SSR 代理层）
```

**前端状态管理**：无全局状态库，使用 React `useState` + `useEffect` 管理页面级状态；`user_id` 持久化在 `localStorage`（key: `faresnipper_user_id`）。

#### 5.2.5 数据库表结构

目标共 11 张业务表（PostgreSQL；现有模型需补充航班缓存与爬虫任务表）：

| 表名 | 主键 | 用途 | 关键字段 |
|------|------|------|---------|
| `user_preferences` | `user_id` (String) | 用户偏好画像 | `budget`, `frequent_cities[]`, `preferred_airlines[]`, `constraints[]` |
| `sessions` | `session_id` (String) | 会话管理 | `user_id`, `last_active_at`（超 30min 过期） |
| `chat_history` | `id` (Int) | 多轮对话上下文 | `session_id`, `role`, `content`，bootstrap 节点读取后转换为 LangGraph `messages` 列表注入 ReAct Agent |
| `query_history` | `id` (Int) | 搜索历史 | `user_id`, `query_text`, `intent`(JSONB)，MemoryPage 展示 |
| `click_history` | `id` (Int) | 点击行为 | `user_id`, `flight_data`(JSONB)，memory_learner 异步读取推断偏好 |
| `price_alerts` | `alert_id` (String) | 价格监控 | `flight_id`, `current_price`, `target_price`, `status` |
| `flight_snapshots` | `id` (String) | 航班聚合快照 | `origin_code`, `destination_code`, `depart_date`, `flight_no`, `lowest_price`, `crawled_at`, `expires_at` |
| `platform_price_snapshots` | `id` (String) | 平台价格快照 | `flight_snapshot_id`, `platform`, `price`, `url`, `raw_payload`, `crawled_at` |
| `crawl_jobs` | `job_id` (String) | 爬虫任务状态 | `route_key`, `depart_date`, `status`, `platform_status`, `started_at`, `finished_at`, `error_message` |
| `intent_registry` | `intent_id` (String) | 意图定义注册表 | `name`, `description`, `required_slots`(JSONB), `optional_slots`(JSONB), `slot_schema`(JSONB), `handler_name`, `is_active` |
| `intent_examples` | `id` (Int) | 意图触发例句库 | `intent_name`, `example_text`, `embedding`(vector 1536，pgvector)，用于 embedding 快速路匹配 |

**intent_registry 表字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `intent_id` | String PK | UUID |
| `name` | String UNIQUE | 意图唯一名称，对应工具函数名（如 `search_flight`） |
| `description` | Text | 中文描述，动态注入 ReAct Agent System Prompt |
| `required_slots` | JSONB | 必填槽位名列表，如 `["origin","destination","depart_date"]` |
| `optional_slots` | JSONB | 选填槽位名列表 |
| `slot_schema` | JSONB | 每个槽位的类型、描述、枚举值，用于动态构建 tool schema |
| `handler_name` | String | 对应的后端工具函数名，bootstrap 时用于动态绑定 |
| `is_active` | Boolean | false 时不加载，软删除/灰度用 |
| `min_examples` | Integer | 激活所需最少例句数（默认 10），未达到则强制 is_active=false |

**intent_examples 表字段说明：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Int PK | 自增 |
| `intent_name` | String FK | 关联 intent_registry.name |
| `example_text` | Text | 触发例句（中文自然语言） |
| `embedding` | vector(1536) | pgvector 存储，插入时自动调 embedding 模型生成 |
| `created_at` | DateTime | 插入时间 |

**Redis 用途**：Session 状态缓存（TTL 30min）；意图注册表缓存（TTL 60s，避免每次请求查 DB）；`aioredis` 异步客户端，连接池在 FastAPI lifespan 阶段初始化。

#### 5.2.6 可靠性设计

**熔断器（Circuit Breaker）**：`backend/resilience/circuit_breaker.py`

三态状态机，作用于每个外部查价数据源：

| 状态 | 触发条件 | 行为 |
|------|---------|------|
| CLOSED（正常） | 初始状态 / 成功后重置 | 请求正常通过 |
| OPEN（熔断） | 连续失败 ≥ 5 次 | 直接拒绝请求，返回空结果 |
| HALF_OPEN（试探） | OPEN 持续 30s 后 | 放行一次请求，成功则 CLOSED，失败则重置 OPEN 计时 |

**超时处理**：超时发生在后台爬虫任务中，单平台超时只标记该平台失败；全部平台失败时不覆盖上一轮有效缓存。用户查询链路只读数据库，命中缓存直接返回，未命中时返回空数组并展示「暂无数据，请重试」。

**LLM 调用兜底**：ReAct Agent 工具调用失败或输出不合规时，以 ToolMessage 写入错误信息，代理可继续推理（如跳过该工具或改调 `show_fallback_form`）；若代理本身无输出，则设 `fallback_triggered=true`，展示兜底表单。

**可观测性**：接入 LangSmith（`LANGCHAIN_TRACING_V2=true`），每次 `graph.invoke()` 自动生成 `run_id` 作为链路追踪 ID，可在 LangSmith Dashboard 查看节点耗时和 LLM 输入输出。

#### 5.2.7 部署架构

| 组件 | 平台 | 说明 |
|------|------|------|
| 前端 | Vercel | Next.js App Router，自动 CI/CD，全球 CDN |
| 后端 API | Railway | FastAPI + uvicorn，容器化部署，支持环境变量热配置 |
| PostgreSQL | Railway（托管） | 自动备份，生产/开发共用同一实例，通过 `DATABASE_URL` 注入 |
| Redis | Railway（托管） | Session 缓存，通过 `REDIS_URL` 注入 |
| LLM | 阿里云 Dashscope | OpenAI-compatible API，国内低延迟，通过 `MODEL_BASE_URL` 切换 |
| 链路追踪 | LangSmith | 可选开启（`LANGCHAIN_TRACING_V2=true`），开发/灰度阶段使用 |

**关键环境变量：**

```bash
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://...
MODEL_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MODEL_API_KEY=sk-xxx
MODEL_AGENT=qwen-plus
MODEL_JUDGE=qwen-plus
SESSION_TTL_MINUTES=30
FLIGHT_CRAWL_INTERVAL_MINUTES=60
FLIGHT_CACHE_TTL_MINUTES=60
LANGCHAIN_TRACING_V2=false      # 生产关闭，开发/灰度开启
LANGCHAIN_API_KEY=ls-xxx
```

### 5.3 功能地图

| 用户目标 | 核心功能 | 支撑功能 | 版本 |
|---------|---------|---------|-----|
| 快速查到便宜票 | 对话查票 + 多平台比价 + 意图追问 | session 多轮上下文 | v1.0 MVP |
| 判断「值不值得买」 | AI 值得买信号 + 一句话建议 + 历史均价对比 | recommend_score 排序 | v1.0 MVP |
| 跳转购买 | 各平台深链跳转 + APP 未安装降级 H5 | — | v1.0 MVP |
| 发现好价机会 | 探索发现页（推荐卡片瀑布流）+ 盲盒功能 | 冷启动热门推荐 | v1.0 MVP |
| 个性化决策 | 偏好自动学习（心理价位/常去城市/偏好航司） | MemoryPage 出行偏好查看与编辑 | v1.0 MVP |
| 不错过好价 | 价格监控（存储意图）| 个人中心监控列表 | v1.0 MVP（不推送）|
| 实时价格提醒 | 价格监控推送通知 | — | v2.0 |
| 历史价格参考 | 价格走势图表 | — | v2.0 |

---

## 6. 0-1 商业模式

**当前阶段目标（v1.0 MVP）**：不做商业化，专注积累真实用户数据和产品口碑，验证核心假设。

**变现路径规划**：

| 阶段 | 版本 | 变现方式 | 预期收入 | 前提条件 |
|------|------|---------|---------|---------|
| 验证期 | v1.0 MVP | 无 | — | — |
| 起步期 | v1.1 | 联盟返佣（携程/去哪儿联盟计划，跳转成单按票价 5-8% 返佣） | 少量 | 月 QPC > 500 |
| 增长期 | v2.0 | 联盟返佣（规模化）+ 会员订阅（价格监控推送、历史价格图表） | 稳定现金流 | 月活 > 5000 |
| 扩张期 | v3.0 | 与OTA深度合作（专属低价资源 + 数据共享）| — | 用户规模足够谈判 |

**联盟返佣说明**：跳转时在深链中携带推广参数（CPS 模式），用户在平台完成购票后按比例分佣，不影响用户体验，也不需要用户额外操作。

---

## 7. MVP 假设清单

在 v1.0 阶段需要验证的核心假设，按优先级排列：

| # | 假设 | 验证方式 | 成立标准 | 优先级 |
|---|------|---------|---------|--------|
| H1 | 用户愿意用对话方式查票（而非表单） | 对话入口 vs 结构化表单 A/B 测试 | 对话完成率高于表单 30% | P0 |
| H2 | AI「值得买」判断能帮用户做决策 | 追踪 AI 建议采纳率（点击建议内的跳转链接） | 采纳率 > 30% | P0 |
| H3 | 用户有意愿跳转到外部平台购买 | 跳转点击率 | > 25% | P0 |
| H4 | 偏好记忆能提升复访（用户感知到「越用越懂我」） | 有偏好数据 vs 无偏好数据用户的 7 日留存对比 | 有偏好用户留存高 20%+ | P1 |
| H5 | 每小时刷新缓存能满足用户对价格新鲜度的预期 | 展示数据更新时间后做用户访谈 + NPS 调研 | NPS > 30，价格新鲜度投诉率 < 5% | P1 |
| H6 | 「探索发现」页可以作为自然流量入口（发现意想不到的好价） | ExplorePage 产生的查询量占比 | > 20% | P2 |

**假设验证计划**：H1-H3 在灰度上线第 1 周验证，H4-H5 在上线 30 天后验证，H6 在 v1.1 版本评估。

---

---

## 8. 流程定义

### 8.1 业务流程

<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 680 680" style="font-family:system-ui,sans-serif;max-width:680px;width:100%">
<defs>
  <style>
    .th{font-size:13px;font-weight:600;fill:#111827}
    .ts{font-size:11px;fill:#6b7280}
    .c-gray{fill:#f3f4f6;stroke:#9ca3af;stroke-width:1.5}
    .c-teal{fill:#ccfbf1;stroke:#0d9488;stroke-width:1.5}
    .c-blue{fill:#dbeafe;stroke:#2563eb;stroke-width:1.5}
    .c-amber{fill:#fef3c7;stroke:#d97706;stroke-width:1.5}
    .c-red{fill:#fee2e2;stroke:#ef4444;stroke-width:1.5}
    .c-blue-dash{fill:#dbeafe;stroke:#2563eb;stroke-width:1.5;stroke-dasharray:5,3}
    .edge{fill:none;stroke:#9ca3af;stroke-width:1.5;marker-end:url(#arrow)}
    .lbl{font-size:11px;fill:#6b7280}
  </style>
  <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
    <path d="M2 1L8 5L2 9" fill="none" stroke="#9ca3af" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
  </marker>
</defs>

<!-- 1. 用户输入 -->
<rect x="250" y="14" width="180" height="36" rx="18" class="c-gray"/>
<text x="340" y="32" text-anchor="middle" dominant-baseline="central" class="th">用户自然语言输入</text>

<line x1="340" y1="50" x2="340" y2="83" class="edge"/>

<!-- 2. 意图理解 -->
<rect x="195" y="83" width="290" height="36" rx="8" class="c-teal"/>
<text x="340" y="101" text-anchor="middle" dominant-baseline="central" class="th">意图理解 Agent（LLM）</text>

<line x1="340" y1="119" x2="340" y2="152" class="edge"/>

<!-- 3. 信息完整？ diamond -->
<polygon points="340,150 408,174 340,198 272,174" class="c-amber"/>
<text x="340" y="174" text-anchor="middle" dominant-baseline="central" class="th">信息完整？</text>

<!-- 不完整 → 追问 -->
<path d="M408 174 L450 174" class="edge"/>
<text x="416" y="166" class="lbl">不完整</text>
<rect x="450" y="156" width="120" height="36" rx="8" class="c-red"/>
<text x="510" y="174" text-anchor="middle" dominant-baseline="central" class="th">追问用户</text>
<!-- 追问 → 回用户输入 右侧绕行 -->
<path d="M570 156 L618 156 L618 32 L430 32" class="edge" stroke-dasharray="4,2"/>
<text x="628" y="95" class="lbl" transform="rotate(90,628,95)">最多2次</text>

<!-- 完整 → 向下分叉 -->
<path d="M340 198 L340 235" class="edge"/>
<text x="348" y="222" class="lbl">完整</text>

<!-- 分叉横线 -->
<line x1="155" y1="235" x2="525" y2="235" stroke="#9ca3af" stroke-width="1.5"/>

<!-- 4a. 比价Agent -->
<line x1="155" y1="235" x2="155" y2="263" class="edge"/>
<rect x="50" y="263" width="210" height="36" rx="8" class="c-blue"/>
<text x="155" y="281" text-anchor="middle" dominant-baseline="central" class="th">比价 Agent（工程）</text>

<!-- 4b. 偏好匹配 -->
<line x1="525" y1="235" x2="525" y2="263" class="edge"/>
<rect x="400" y="263" width="250" height="36" rx="8" class="c-teal"/>
<text x="525" y="281" text-anchor="middle" dominant-baseline="central" class="th">偏好匹配（工程规则）</text>

<!-- 汇聚到判断Agent -->
<path d="M155 299 L155 358 L300 358" class="edge"/>
<path d="M525 299 L525 358 L380 358" class="edge"/>

<!-- 5. 判断Agent -->
<rect x="195" y="358" width="290" height="36" rx="8" class="c-teal"/>
<text x="340" y="376" text-anchor="middle" dominant-baseline="central" class="th">判断 Agent（LLM）</text>

<line x1="340" y1="394" x2="340" y2="427" class="edge"/>

<!-- 6. 生成结果 -->
<rect x="210" y="427" width="260" height="36" rx="8" class="c-blue"/>
<text x="340" y="445" text-anchor="middle" dominant-baseline="central" class="th">生成结果</text>

<!-- 分叉 -->
<path d="M340 463 L340 497" stroke="#9ca3af" stroke-width="1.5" fill="none"/>
<line x1="155" y1="497" x2="525" y2="497" stroke="#9ca3af" stroke-width="1.5"/>

<!-- 7a. 输出给用户 -->
<line x1="155" y1="497" x2="155" y2="527" class="edge"/>
<rect x="40" y="527" width="230" height="36" rx="8" class="c-blue"/>
<text x="155" y="545" text-anchor="middle" dominant-baseline="central" class="th">输出结果给用户</text>

<!-- 7b. 记忆更新 -->
<line x1="525" y1="497" x2="525" y2="527" class="edge"/>
<rect x="395" y="527" width="250" height="36" rx="8" class="c-blue-dash"/>
<text x="520" y="545" text-anchor="middle" dominant-baseline="central" class="th">异步记忆更新</text>

<!-- 汇聚END -->
<path d="M155 563 L155 634 L300 634" class="edge"/>
<path d="M525 563 L525 634 L380 634" class="edge"/>
<text x="535" y="600" class="ts">失败不阻塞主流程</text>

<!-- 8. END -->
<rect x="260" y="622" width="160" height="36" rx="18" class="c-gray"/>
<text x="340" y="640" text-anchor="middle" dominant-baseline="central" class="th">END</text>
</svg>

### 8.2 节点说明

| Node | 类型 | 流转（Edge） | 备注 |
|------|------|-------------|------|
| 用户自然语言输入 | 工程 | → 意图理解 | 无格式限制，支持文本输入 |
| 意图理解 Agent | LLM | 成功 → 信息完整判断；解析失败 → END（兜底提示） | 解析出发地/目的地/时间/预算/约束 |
| 信息完整？ | 工程 | 完整 → 并行执行；不完整 → 追问 | 必填：出发地、目的地、时间范围 |
| 追问用户 | 工程 | → 用户输入 | 最多追问2次，超限降级为结构化表单 |
| 比价 Agent | 工程 | → 判断 Agent | 读取航班价格缓存；爬虫每 1 小时后台刷新数据库 |
| 偏好匹配 Agent | 工程 | → 判断 Agent | 读取用户偏好记忆，按规则计算每条结果的匹配度 |
| 判断 Agent | LLM | → 生成结果 | 综合价格+历史均价+偏好，输出值得买信号 |
| 生成结果 | 工程 | → 输出给用户 + 异步记忆更新 | 记忆更新异步执行，不阻塞主链路 |
| 异步记忆更新 | 工程 | → END | 写入失败静默忽略，不影响主流程 |

---

## 9. 功能点详细说明

### 9.1 Agent State 设计

采用 ReAct 模式后，`WorkflowState` 以 `messages` 列表为核心，消息历史即推理上下文。`accumulated_slots` 负责跨轮槽位的持久化。

**完整字段说明：**

| 分类 | 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| ReAct 核心 | messages | `list[BaseMessage]` | 是 | LangGraph `add_messages` 操作，自动追加不覆盖；包含 HumanMessage / AIMessage / ToolMessage |
| 用户标识 | request_user_id | string | 是 | 用户ID，由后端分配匿名ID，见 9.8 |
| 用户标识 | request_session_id | string | 否 | 对话会话ID，为 null 时后端新建，见 9.9 |
| 槽位 | accumulated_slots | `SlotBundle` | 否 | 跨轮累积的槽位状态，从 Redis 恢复；ask_user 时更新并写回 Redis |
| 控制 | clarify_count | integer | 是 | ask_user 工具被调用次数，默认0；≥2 时代理收到提示改用降级表单工具 |
| 控制 | fallback_triggered | boolean | 是 | 是否已触发结构化表单降级，默认 false |
| 工具结果 | search_result | `FlightSearchResult` | 否 | search_flights 工具执行后填充 |
| 工具结果 | pref_result | `PreferenceMatchResult` | 否 | get_preferences 执行后填充（工程规则匹配） |
| 工具结果 | decision | `DecisionResult` | 否 | judge_value 工具执行后填充 |
| 响应 | response | `FrontendResponse` | 否 | 最终写回前端的结构化响应 |
| 错误 | errors | `list[WorkflowError]` | 是 | 各工具执行异常收集，不中断流程 |

**SlotBundle 数据结构（`application/contracts/slots.py`）：**

```python
@dataclass
class SlotBundle:
    intent: str | None = None          # search_flight / set_alert / check_preference / update_preference
    origin: str | None = None          # 出发城市（中文）
    destination: str | None = None     # 目的地城市（中文）
    depart_date: str | None = None     # YYYY-MM-DD
    return_date: str | None = None     # YYYY-MM-DD，null 表示单程
    cabin_class: str | None = None     # economy / business / first
    passengers: int = 1
    budget: int | None = None          # 单程预算上限（元）
    constraints: list[str] = field(default_factory=list)  # avoid_redeye / direct_only / prefer_morning
    target_price: int | None = None    # 仅 set_alert 意图使用
```

**跨轮槽位合并规则：**

```python
def merge_slots(accumulated: SlotBundle, new_slots: dict) -> SlotBundle:
    merged = copy.copy(accumulated)
    for k, v in new_slots.items():
        if v is not None:          # null 不覆盖已有值
            setattr(merged, k, v)
    return merged
```

> **注**：`trace_id` 由 LangSmith 在每次 `graph.invoke()` 时自动生成 `run_id`，无需注入 State。防死循环用 `recursion_limit=20`，通过 `graph.invoke(config={"recursion_limit": 20})` 传入。

### 9.2 意图识别与 Slot Filling

采用 **Slot Filling + 多轮累积** 方案。ReAct 代理在每轮对话中提取槽位，通过 `ask_user` 工具补全必填槽，槽位跨轮合并直到完整再触发搜索。

#### 9.2.1 意图枚举

| 意图值 | 触发场景 | 备注 |
|--------|---------|------|
| `search_flight` | 查机票价格 | 最核心意图 |
| `set_alert` | 设置价格提醒 | 需额外 target_price 槽 |
| `check_preference` | 查看偏好记忆 | 无需槽位 |
| `update_preference` | 修改偏好设置 | 至少一个偏好字段 |
| `chitchat` | 闲聊/问候 | 直接回复，不调工具 |

#### 9.2.2 各意图的槽位要求

| 槽位 | search_flight | set_alert | 说明 |
|------|:---:|:---:|------|
| origin | **必填** | **必填** | 出发城市（中文） |
| destination | **必填** | **必填** | 目的地城市（中文） |
| depart_date | **必填** | **必填** | 出发日期 YYYY-MM-DD |
| return_date | 选填 | — | 有值表示往返 |
| cabin_class | 选填 | — | economy / business / first，默认 economy |
| passengers | 选填 | — | 整数，默认 1 |
| budget | 选填 | — | 单程上限（元） |
| constraints | 选填 | — | 见约束枚举表 |
| target_price | — | **必填** | 触发通知的目标价（元） |

**约束条件枚举：**

| 枚举值 | 触发词示例 | 说明 |
|--------|-----------|------|
| `avoid_redeye` | "不要太早"/"不要红眼" | 起飞时间须 ≥ 06:00 |
| `direct_only` | "直飞" | 不展示中转航班 |
| `prefer_morning` | "早点到" | 优先到达时间 < 12:00 的航班 |

#### 9.2.3 多轮槽位累积流程

追问文案由 ReAct Agent 根据当前对话上下文动态生成，不使用固定模板。

```
Turn 1: "帮我找下周去三亚的机票"
  代理推理: intent=search_flight
            已提取: destination=三亚, depart_date=2026-05-11
            缺少: origin
            上下文感知生成问题 → "下周去三亚！从哪里出发？"
  → ask_user(question="下周去三亚！从哪里出发？", missing_slots=["origin"])
  → 保存 accumulated_slots={intent:"search_flight", destination:"三亚", depart_date:"2026-05-11"}

Turn 2: "北京"
  代理推理: 提取 origin=北京
            合并 → {origin:"北京", destination:"三亚", depart_date:"2026-05-11"}
            必填槽全部完整
  → search_flights(origin="北京", destination="三亚", depart_date="2026-05-11")
```

**上下文感知追问示例对照：**

| 用户输入 | 已知槽 | 缺失槽 | ❌ 固定模板 | ✅ 上下文生成 |
|---------|--------|--------|-----------|------------|
| 帮我找机票 | 无 | origin | 请问您从哪个城市出发？ | 从哪儿出发？ |
| 帮我找去三亚的票 | destination | origin | 请问您从哪个城市出发？ | 去三亚！从哪里出发？ |
| 国庆想出去玩 | depart_date | origin | 请问您从哪个城市出发？ | 国庆出游！从哪出发？ |
| 北京出发想找便宜票 | origin | destination | 请问目的地是哪里？ | 北京出发，想去哪儿？ |
| (第二轮补充了 origin=北京) | origin+destination | depart_date | 请问什么时间出发？ | 北京→三亚，哪天走？ |

**关键规则：**
- 每次 `ask_user` 只问一个最重要的缺失槽（优先级：origin → destination → depart_date）
- 问题要承接上下文：已知的信息自然融入，不重复询问
- `clarify_count ≥ 2` 时，代理改调 `show_fallback_form` 工具弹出 Modal，不再追问
- 已填槽不重复询问；新值覆盖旧值，`null` 值不覆盖

#### 9.2.4 时间表述映射（兜底映射表，代理推算优先）

| 表述 | 映射规则 |
|------|---------|
| 五一 | 2026-05-01 ~ 2026-05-05 |
| 清明 | 2026-04-04 ~ 2026-04-06 |
| 国庆 | 2026-10-01 ~ 2026-10-07 |
| 下周末 | 最近的周六~周日 |
| 本周末 | 本周六~周日 |
| 下周五 | 推算当前日期后第一个周五 |

### 9.2.5 Tool 定义

代理可调用的工具列表（`application/tools/`）：

**`ask_user`**

```python
def ask_user(question: str, missing_slots: list[str]) -> str:
    """
    向用户提问补全缺失槽位。
    调用后图停止等待用户下一轮输入，结果以 ToolMessage 写回 messages。
    同时将当前 accumulated_slots 写入 Redis（session TTL 内持久化）。

    question 由 ReAct Agent 根据上下文动态生成，不使用固定模板。
    生成规则见 §10.1 System Prompt「追问风格」章节。
    """
```

| 参数 | 类型 | 说明 |
|------|------|------|
| question | string | **LLM 动态生成**的追问文案，需承接上下文，≤ 20 字，只问一项缺失信息 |
| missing_slots | list[str] | 当前缺失的必填槽名列表，供前端高亮提示（如输入框 placeholder） |

**`search_flights`**

```python
def search_flights(
    origin: str, destination: str, depart_date: str,
    return_date: str | None = None,
    cabin_class: str = "economy",
    passengers: int = 1,
    constraints: list[str] = []
) -> FlightSearchResult:
    """
    并行查询多个数据源，单源超时 3s 跳过，返回 FlightSearchResult。
    结果同时写入 state["search_result"] 供后续工具引用。
    """
```

**`get_preferences`**

```python
def get_preferences() -> UserPreference:
    """
    从 PostgreSQL 读取当前用户偏好记忆。
    结果写入 state["pref_result"]（经工程规则匹配后）。
    新用户返回空偏好对象，不触发错误。
    """
```

**`judge_value`**

```python
def judge_value() -> DecisionResult:
    """
    读取 state["search_result"] 和 state["pref_result"]，
    调用 ValueJudge LLM（qwen-plus）生成值得买建议。
    结果写入 state["decision"]。
    """
```

**`show_fallback_form`**

```python
def show_fallback_form() -> str:
    """
    clarify_count ≥ 2 时触发。
    设置 state["fallback_triggered"] = True，
    前端收到信号后弹出结构化填写 Modal（不跳页）。
    """
```

### 9.2.6 动态意图注册表

意图定义存在数据库中，无需改代码即可上线新意图的**识别能力**（执行逻辑仍需代码发布）。

#### 动态更新的两层结构

| 层 | 内容 | 更新方式 | 生效时间 |
|---|------|---------|---------|
| **识别层** | 意图名称、描述、槽位 schema、触发例句 | 写 DB | ≤ 60s（Redis TTL） |
| **执行层** | 工具函数实现、handler 逻辑 | 代码发布 | 发布后 |

识别层和执行层解耦：可以先上线识别（DB 写入），执行代码未就绪时降级到「已识别但暂不支持，请稍后」，不崩溃。

#### 运行时加载流程（bootstrap 节点）

```python
async def load_intent_registry(redis, db) -> list[IntentDef]:
    cached = await redis.get("intent_registry:active")
    if cached:
        return json.loads(cached)

    intents = await db.query(
        IntentRegistry,
        where=[IntentRegistry.is_active == True]
    )
    await redis.setex("intent_registry:active", 60, json.dumps(intents))
    return intents

def build_tool_schemas(intents: list[IntentDef]) -> list[dict]:
    """将 intent_registry 动态转换为 LLM function calling schema"""
    tools = []
    for intent in intents:
        tools.append({
            "type": "function",
            "function": {
                "name": intent.name,
                "description": intent.description,
                "parameters": {
                    "type": "object",
                    "properties": intent.slot_schema,
                    "required": intent.required_slots
                }
            }
        })
    return tools

# bootstrap 时
intent_defs = await load_intent_registry(redis, db)
tool_schemas = build_tool_schemas(intent_defs)
llm_with_tools = base_llm.bind_tools(tool_schemas)  # 运行时绑定，非代码写死
```

#### Embedding 快速路（高置信度跳过 LLM）

```python
async def fast_intent_match(user_input: str, db) -> IntentMatch | None:
    query_vec = await embed(user_input)            # 调 embedding 模型，< 10ms
    result = await db.vector_search(
        table=IntentExamples,
        vector=query_vec,
        top_k=1,
        similarity="cosine"
    )
    if result and result[0].score > 0.85:
        return IntentMatch(
            intent_name=result[0].intent_name,
            confidence=result[0].score,
            source="embedding"
        )
    return None  # fallback 到 ReAct Agent

# bootstrap 时
fast_match = await fast_intent_match(user_input, db)
if fast_match:
    # 高置信度：注入 messages 告知代理，代理直接跳到 slot 提取
    state["messages"].append(SystemMessage(
        content=f"[系统提示] 用户意图已预判为 {fast_match.intent_name}（置信度 {fast_match.confidence:.2f}），请直接提取槽位或执行工具。"
    ))
```

```
用户输入
  │
  ├─ Embedding 检索（< 10ms）
  │   └─ score > 0.85 → 注入预判提示，代理快速路（跳过意图推理，直接槽位提取）
  │
  └─ score ≤ 0.85 → ReAct Agent 完整推理（动态 tool schema）
```

#### 新意图上线操作步骤

```
1. 写 intent_registry 表（is_active=false）
   → 填写 name / description / required_slots / optional_slots / slot_schema / handler_name

2. 写 intent_examples 表（至少 10 条触发例句）
   → embedding 自动生成（插入 trigger 后台任务处理）

3. 达到 min_examples 阈值后将 is_active 改为 true
   → 60s 内所有新请求自动加载新意图

4. 上线对应 handler 代码（可与步骤 3 并行）
   → handler 未就绪时：执行层返回「该功能正在建设中」，识别层正常工作
```

#### 冷启动质量要求

| 条件 | 说明 |
|------|------|
| 最少例句数 | ≥ 10 条，覆盖不同表达方式（口语/书面/缩写） |
| 例句多样性 | 不要全部相似；要包含边界表达，如「帮我查票」这种无槽位的模糊输入 |
| 描述清晰度 | `description` 字段要让 LLM 能区分该意图与其他意图，举例说明 |
| 槽位 schema | `slot_schema` 里每个槽位要有 `description` 和 `type`，有枚举值的加 `enum` |

#### 管理接口（Admin API，非用户侧）

| 接口 | 方法 | 说明 |
|------|------|------|
| `/api/admin/intents` | GET | 列出所有意图（含非激活） |
| `/api/admin/intents` | POST | 新增意图定义 |
| `/api/admin/intents/{name}` | PATCH | 更新意图（含切换 is_active） |
| `/api/admin/intents/{name}/examples` | POST | 批量添加例句（后台异步生成 embedding） |
| `/api/admin/intents/cache/invalidate` | POST | 手动清除 Redis 缓存（立即生效，不等 60s TTL） |

### 9.3 比价技能

比价技能使用工程侧真实航班数据，消费爬虫模块或后续官方/代理 API 产出的查询结果。接口层保留统一数据源适配层，负责把不同平台的原始返回归一化为前端和推荐链路可消费的航班价格结构。

**当前工程现状：**
- 搜索主链路位于 `backend/application/graph/nodes/fetch_flights.py`，当前从意图解析结果中读取出发地、目的地和日期，再生成 `FlightSearchResult`。
- 数据源抽象已存在：`backend/data_sources/base.py` 定义 `DataSource`，`backend/data_sources/registry.py` 提供注册表，适合承接多平台真实数据源。
- 携程适配层已存在：`backend/data_sources/ctrip_source.py` 已实现 `CtripSource.search_flights()`、字段归一化 `_normalize()`、历史价格接口 `get_history_prices()`。
- 工程爬虫能力集中在 `backend/third_party/flights_monitor/`：包含 `CtripScraper`、`QunarScraper`、`FliggyScraper`、`TongchengScraper`、`UmetripScraper` 等平台爬虫，以及 `multi_platform.py` 中的 `MultiPlatformClient/search_multiplatform()` 聚合入口。
- 多平台爬虫统一输出原始字段：`flight_number`、`airline`、`dep_city`、`arr_city`、`dep_time`、`arr_time`、`duration`、`transfer_count`、`price`、`discount_rate`、`date`、`platform`。
- 当前数据库已有 `user_preferences`、`query_history`、`click_history`、`chat_history`、`sessions`、`price_alerts` 等表；还缺少航班结果缓存表、平台价格快照表和爬虫任务状态表。

**数据来源：**
- 首期接入工程目录中的 `flights_monitor` 爬虫能力，优先使用已跑通的平台适配器；爬虫以后台任务形式运行，不阻塞用户查询请求。
- 当前目标平台：携程、去哪儿、飞猪；若某平台因反爬、登录态、网络或页面结构变化不可用，则该平台当次结果为空，不影响其他平台结果返回。
- 查询输入来自意图识别后的标准字段：出发城市/机场码、到达城市/机场码、出发日期、返程日期或日期窗口、直飞等约束。
- 爬虫返回的原始字段必须经过统一归一化，再进入推荐、偏好匹配和值得买判断链路。

**数据刷新策略：**
- 爬虫任务按固定频率刷新数据，MVP 默认每 1 小时执行一次。
- 用户发起查询时不现场触发爬虫，只从数据库读取最近一次成功入库的数据。
- 每条缓存数据必须记录 `crawled_at` 和 `expires_at`；默认 `expires_at = crawled_at + 1h`。
- 若查询命中数据已过期但仍有可用缓存，可返回缓存结果，并在响应 `meta.data_freshness` 中标记为 `stale`；前端可展示"数据更新时间"。
- 若数据库无匹配航线/日期数据，返回空数组，前端展示"暂无数据，请重试"或引导用户换日期。
- 定时爬取范围优先覆盖高频航线和用户近期查询过的航线，避免全量航线爬取导致成本和反爬风险过高。

**定时爬取范围：**
- 固定高频航线池：北京↔成都、北京↔三亚、北京↔上海、北京↔广州、北京↔杭州。
- 动态热门航线池：从 `query_history` 中统计近 7 天查询频次 Top N 航线，加入下一轮爬取队列。
- 价格提醒航线池：从 `price_alerts` 中读取 `status=active` 的航线和日期，加入高优先级爬取队列。
- 日期窗口：默认爬取未来 1-30 天；节假日、周末和价格提醒日期可扩展到未来 90 天。

**查询链路：**
```
用户输入
  → ReAct Agent 提取 origin/destination/depart_date/constraints
  → FlightCacheRepository 查询数据库缓存
  → 命中可用数据：返回归一化航班列表
  → 未命中：返回空数组，不同步启动爬虫
  → PreferenceMatch / ValueJudge / RenderResponse
```

**爬取链路：**
```
Scheduler 每 1h 触发
  → 生成 CrawlJob（高频航线 + 热门查询 + 价格提醒）
  → MultiPlatformClient 调用各平台爬虫
  → Normalizer 统一字段
  → Upsert flight_snapshots / platform_price_snapshots
  → 更新 crawl_jobs 状态和 platform_status
```

**新增数据库表建议：**

| 表名 | 用途 | 关键字段 |
|------|------|----------|
| `flight_snapshots` | 存储按航班聚合后的查询结果 | `id`、`origin_code`、`destination_code`、`depart_date`、`flight_no`、`airline`、`dep_time`、`arr_time`、`duration`、`stops`、`lowest_price`、`history_avg_90d`、`history_low_90d`、`crawled_at`、`expires_at` |
| `platform_price_snapshots` | 存储同一航班在不同平台的价格 | `id`、`flight_snapshot_id`、`platform`、`price`、`url`、`raw_payload`、`crawled_at` |
| `crawl_jobs` | 记录每轮爬虫任务状态 | `job_id`、`route_key`、`origin_code`、`destination_code`、`depart_date`、`status`、`platform_status`、`started_at`、`finished_at`、`error_message` |

**缓存命中规则：**
- 主查询条件：`origin_code + destination_code + depart_date`。
- 直飞筛选：查询后按 `stops=0` 过滤。
- 平台价格列表：通过 `flight_snapshot_id` 关联 `platform_price_snapshots`，按价格升序组装 `prices[]`。
- 去重键：`origin_code + destination_code + depart_date + flight_no + dep_time`。
- 同一去重键重复入库时执行 upsert，保留最新一轮 `crawled_at` 的数据。

**数据覆盖要求：**
- 支持范围以爬虫平台实时可查询范围为准。
- 若用户查询北京↔成都、北京↔三亚、北京↔上海、北京↔广州、北京↔杭州等高频航线，应调用爬虫查询真实结果。
- 每条航线的航班数量以平台实际返回为准，不强制每天 2-3 个航班。
- 平台间价差以真实抓取结果为准。
- 近 90 天历史均价和历史最低价仅在工程侧存在真实历史数据时返回；暂无真实历史数据时字段返回 `null`。

**工程改造方向：**
- 新增或改造统一真实数据源适配器，例如 `MultiPlatformFlightSource`，内部调用 `search_multiplatform()`，对外实现 `DataSource.search_flights()`。
- 新增后台爬虫调度器，例如 `FlightCrawlScheduler`，按 1 小时频率生成任务并调用 `MultiPlatformFlightSource`。
- 新增数据库读模型，例如 `FlightCacheRepository`，供用户查询链路读取 `flight_snapshots` 和 `platform_price_snapshots`。
- 将 `fetch_flights.py` 的查价入口改为读取 `FlightCacheRepository`，而不是在用户请求内直接绑定或调用某个具体平台爬虫。
- 将 `flights_monitor` 原始字段统一映射为业务字段：`flight_number → flight_no`、`dep_time → dep_time`、`arr_time → arr_time`、`transfer_count → stops`、`platform + price → prices[]`。
- 在适配层完成同航班聚合、最低价计算、异常平台过滤和字段补齐，Graph 节点只消费归一化后的航班列表。
- 历史价格能力单独抽象为 `HistoryPriceSource` 或复用 `DataSource.get_history_prices()`；没有真实历史数据时保持空值，由 ValueJudge 跳过历史低价信号。
- 平台可用性、超时和错误日志在爬虫任务层处理，并在 `crawl_jobs.platform_status` 与响应 `meta` 中保留 `source`、`data_freshness`、`crawled_at`、`request_id`，便于定位数据质量问题。

**平台聚合规则：**
- 每个平台独立请求，单个平台超时或失败只影响该平台。
- 同一航班按 `flight_no + dep_time + depart_date` 聚合。
- `prices` 保留各平台真实价格；`lowest_price` 取可用平台中的最低价。
- 若同一平台返回多个舱位或价格包，MVP 阶段取成人经济舱最低可购价格。
- 排序默认按 `lowest_price + tax + baggage_fee` 升序，再进入推荐分排序。

**返回字段结构：**

```json
{
  "flight_no": "HU7833",
  "airline": "海南航空",
  "dep_time": "09:30",
  "arr_time": "14:20",
  "duration": "4h50m",
  "stops": 0,
  "prices": [
    {"platform": "携程", "price": 389, "url": "https://..."},
    {"platform": "去哪儿", "price": 399, "url": "https://..."},
    {"platform": "飞猪", "price": 410, "url": "https://..."}
  ],
  "lowest_price": 389,
  "history_avg_90d": 584,
  "history_low_90d": 312
}
```

**字段规则：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `flight_no` | string | 是 | 航班号，来自爬虫原始结果 |
| `airline` | string | 是 | 航司名称 |
| `dep_time` / `arr_time` | string | 是 | 起降时间，统一为 `HH:mm` |
| `duration` | string | 是 | 飞行时长，统一为 `4h50m` 格式 |
| `stops` | integer | 是 | 经停/中转次数，直飞为 0 |
| `prices` | array | 是 | 各平台真实价格列表，仅包含本次成功返回的平台 |
| `lowest_price` | integer | 是 | 本航班各平台最低价 |
| `history_avg_90d` | integer/null | 否 | 真实历史 90 天均价；无数据返回 `null` |
| `history_low_90d` | integer/null | 否 | 真实历史 90 天最低价；无数据返回 `null` |

**超时处理：**

| 场景 | 处理方式 |
|------|---------|
| 单个平台爬取超时 | 该平台本轮标记失败，用其他平台结果继续入库 |
| 全部平台爬取失败 | 不覆盖上一轮有效缓存；记录 `crawl_jobs.status=failed` |
| 查询命中未过期缓存 | 直接返回数据库结果 |
| 查询命中过期缓存 | 可返回缓存结果，并标记 `meta.data_freshness=stale` |
| 查询无缓存数据 | 返回空数组，前端展示"暂无数据，请重试" |
| 爬虫无匹配航线 | 返回空数组，前端展示"暂无数据，请重试" |
| 单个平台字段缺失 | 丢弃该平台该条异常价格，不影响同航班其他平台价格 |
| 爬虫模块异常 | 记录错误日志和 request_id，不影响用户查询链路读取上一轮缓存 |

### 9.4 偏好匹配技能

读取用户偏好记忆，对每条航班结果逐条计算匹配情况。

**匹配规则：**

| 偏好类型 | 匹配条件 | 输出文案 |
|---------|---------|---------|
| 心理价位 | lowest_price ≤ user.budget | ✓ 在你的心理价位以内 |
| 避免红眼 | dep_time ≥ "06:00" 且 user有avoid_redeye | ✓ 符合你的出行习惯 |
| 偏好航司 | airline in user.preferred_airlines | ✓ 你常飞的[航司名] |
| 常去城市 | destination in user.frequent_cities | 不输出文案，仅影响排序权重（靠前） |

**偏好来源展示：**
- 偏好来源展示在前端 MemoryPage 的「出行偏好」章节，而不是展示在搜索结果卡片里。
- 「出行偏好」章节的每条偏好卡片都必须展示：偏好名称、当前值、来源类型、形成依据、更新时间。
- 来源类型分为：
  - `manual`：用户在 MemoryPage 手动编辑或确认的偏好。
  - `query_history`：由用户搜索行为推断，例如多次搜索同一目的地形成常去城市。
  - `click_history`：由用户点击/跳转行为推断，例如多次点击某航司形成偏好航司，最近点击价格形成心理价位。
  - `system_inferred`：由系统规则综合推断，例如连续选择非红眼航班形成避免红眼偏好。
- 展示位置：MemoryPage 打开记忆后，左侧章节选择「偏好 / 出行偏好」，中间 timeline 每条记录展示来源；右侧「这一页的记忆重点」只展示偏好摘要，不承担来源解释。
- 展示文案示例：
  - 心理价位：`当前记录：¥600以内｜来源：最近5次点击票价中位数｜更新于 2026-05-06`
  - 常去城市：`当前记录：三亚、成都｜来源：近7天搜索过3次以上｜更新于 2026-05-06`
  - 偏好航司：`当前记录：海南航空｜来源：近30天点击过2次｜更新于 2026-05-06`
  - 避免红眼：`当前记录：避免 00:00-06:00 出发｜来源：连续3次选择白天航班｜更新于 2026-05-06`

**新用户处理（memories 列表为空时）：**
- preference_matched 返回空数组
- 判断节点跳过偏好维度，结果卡片不展示偏好相关文案
- ExplorePage / 推荐卡片中的「根据你的偏好」模块隐藏或降级为热门路线
- 判断标准：直接检查后端 memories 是否为空，不依赖 query_count

### 9.5 记忆设计

**存储位置：后端数据库（PostgreSQL）**

所有用户偏好和历史数据存在后端 DB，通过 `/api/memory` 系列接口读写。前端不直接读写 localStorage 存偏好，只在 localStorage 里缓存 `user_id`（见 9.8）。

**后端存储的记忆字段：**

| field | 类型 | 说明 |
|-------|------|------|
| budget | number | 心理价位（元） |
| frequent_cities | string[] | 常去城市列表 |
| preferred_airlines | string[] | 偏好航司列表 |
| constraints | string[] | 出行习惯枚举 |
| travel_scenes | string[] | 出行场景枚举 |
| query_history | object[] | 搜索历史（含 text + created_at） |
| click_history | object[] | 点击历史（含 flight_info + created_at） |

**记忆来源字段：**

每条偏好记忆需要保留来源解释，前端 MemoryPage 用它解释系统为什么记住这条偏好。

| 字段 | 类型 | 说明 |
|------|------|------|
| source | enum | 来源类型：`manual` / `query_history` / `click_history` / `system_inferred` |
| source_label | string | 前端展示用来源文案，如「最近5次点击票价中位数」 |
| evidence | object[] | 形成该偏好的证据列表，如关联的查询、点击、航班号、价格 |
| confidence | number | 推断置信度，0-1；手动设置为 1 |
| updated_at | string | 最近更新时间 |

**记忆更新逻辑（异步，用户不感知）：**

| 用户行为 | 更新字段 | 更新规则 |
|---------|---------|---------|
| 查询某目的地 | frequent_cities | 同一城市出现 ≥3次 → 加入列表 |
| 点击某张票 | budget | 取最近5次点击价格的中位数（四舍五入到整十） |
| 多次查询非红眼时段 | constraints | 连续3次查询dep_time≥06:00 → 推断avoid_redeye |
| 点击某航司的票 | preferred_airlines | 同一航司点击 ≥2次 → 加入列表 |

**个人中心用户可操作项：**
- 查看所有偏好条目（5类：常去城市、心理价位、偏好航司、出行习惯、出行场景）
- 每条偏好可逐条编辑
- 「清除所有记忆」一键重置，并弹出确认弹窗（不可逆操作）

### 9.6 值得买信号体系

**判断逻辑（按优先级）：**

| 信号 | 触发条件 | 展示文案 |
|------|---------|---------|
| 历史低价 | lowest_price < history_avg_90d × 0.85 | 🔥 近90天最低，比均价低X% |
| 节假日稀缺 | 出行日为法定节假日（`is_holiday=true`）| ⚡ 节假日难得低价（**MVP 前端不渲染该标签，`is_holiday` 仍传入 ValueJudge 供 advice 文案参考，signals 数组中不输出该值**）|
| 符合心理价位 | lowest_price ≤ user.budget | ✓ 在你的心理价位以内 |
| 符合出行习惯 | 见偏好匹配表 | ✓ 符合你的出行习惯 |

**一句话购买建议生成规则：**

| 触发信号组合 | advice 文案（≤20字） |
|------------|---------------------|
| 历史低价 + 符合心理价位 | 建议现在买，比均价低X%且在预算内 |
| 历史低价，但超预算 | 历史低位，但超出预算X元 |
| 仅符合心理价位，价格正常 | 在预算内，价格正常可继续关注 |
| 无信号触发 | 价格正常，可继续关注 |
| 历史数据不足 | 数据有限，仅供参考 |

### 9.7 异常处理

| 异常场景 | 触发条件 | 处理方式 |
|---------|---------|---------|
| 意图解析失败 | ReAct Agent 无法识别有效槽位或输出为空 | 展示"没听明白，换个说法试试？"，提供表单入口 |
| 比价数据为空 | 全平台超时/无匹配航线 | 展示"暂未找到航班，试试换个日期" |
| 偏好记忆读取失败 | 后端 /api/memory 接口失败 | 跳过偏好维度，正常展示价格结果，不报错 |
| 判断Agent超时（>5s） | LLM响应超时 | 跳过AI建议，仅展示价格数据，结论位置展示"分析中…" |
| 记忆写入失败 | 后端 DB 写入异常 | 静默忽略，下次查询时重试 |
| 追问超限 | clarify_count ≥ 2 | 降级到结构化表单，展示"填一下这几项吧" |

### 9.8 用户身份（user_id）生命周期

**分配方式：后端分配匿名 ID，通过首次 API 响应下发**

1. 用户首次访问，前端发任意 API 请求（或初始化时调 `POST /api/session/init`）
2. 后端检测请求中无有效 user_id → 生成 UUID 并写入响应体
3. 前端收到 user_id 后存入 `localStorage`（key = `faresnipper_user_id`）
4. 后续所有请求从 localStorage 读取 user_id 携带到请求体中

**前端伪代码：**

```typescript
function getUserId(): string {
  let id = localStorage.getItem('faresnipper_user_id')
  if (!id) {
    // 等待首次 API 返回后再存，或先用临时 ID
  }
  return id ?? 'pending'
}
```

**约束：**
- MVP 不做账号体系，user_id 是匿名标识，换浏览器/设备后数据不共享
- user_id 只要 localStorage 不被清除就持续有效
- 后端收到未知 user_id 时，自动创建新用户数据，不报错

### 9.9 多轮对话（session）设计

**机制：后端维护 session，前端传 session_id**

| 步骤 | 行为 |
|------|------|
| 用户点击「历史对话」清空或开始新话题 | 前端调 `POST /api/session` 获取新 session_id |
| 用户每次发消息 | POST /api/search 请求体携带 session_id |
| 后端收到 session_id | 查询该 session 的历史消息，拼入 ReAct Agent 上下文 |
| 追问场景 | 后端在 session 历史里找到上一轮缺失字段，追问只补缺失项 |
| session 过期 | 超过 30 分钟无活动后 session 失效；前端下次请求时后端返回 session_expired 错误，前端自动创建新 session |

**新增接口：POST /api/session**

```json
请求：{ "user_id": "xxx" }
响应：{ "session_id": "uuid", "created_at": "..." }
```

**POST /api/search 请求体更新（加 session_id）：**

```json
{
  "user_id": "xxx",
  "session_id": "yyy",
  "message": "五一去三亚，预算600"
}
```

### 9.10 价格监控（MVP 基础版）

用户在航班卡片点击「监控价格」，后端记录该监控意图。MVP 阶段不做实时推送，仅存储监控列表，供个人中心展示。

**交互流程：**
1. 用户点击卡片上「监控价格」按钮
2. 前端调 `POST /api/alerts`，传入航班信息 + 用户当前出价（最低价）
3. 后端存储监控记录，返回成功
4. 个人中心「价格监控」节点调 `GET /api/alerts` 展示监控列表

**POST /api/alerts 请求：**

```json
{
  "user_id": "xxx",
  "flight_id": "HU7833-20260501",
  "origin_city": "北京",
  "destination_city": "三亚",
  "depart_date": "2026-05-01",
  "current_price": 449,
  "target_price": 400
}
```

**POST /api/alerts 响应：**

```json
{
  "alert_id": "alert-uuid",
  "status": "active",
  "created_at": "2026-04-18T10:00:00Z"
}
```

**GET /api/alerts 响应：**

```json
{
  "user_id": "xxx",
  "alerts": [
    {
      "alert_id": "alert-uuid",
      "origin_city": "北京",
      "destination_city": "三亚",
      "depart_date": "2026-05-01",
      "current_price": 449,
      "target_price": 400,
      "status": "active",
      "created_at": "2026-04-18T10:00:00Z"
    }
  ]
}
```

**MVP 限制：**
- 不做实时价格追踪和推送通知
- 只展示监控列表，不判断是否达到目标价
- 用户可查看已创建的监控（GET /api/alerts），不可编辑
- DELETE /api/alerts/{alert_id} 支持取消监控（v1.1 实现）

---

## 10. Prompt 设计

### 10.0 Prompt 汇总

| Prompt / Agent 名称 | 用途 | 调用节点 | 模型 |
|-------------------|------|---------|------|
| ReAct Agent | 对话核心代理：意图理解 + 槽位补全 + 工具编排 | `react_agent` 节点 | 环境变量 `MODEL_AGENT`，需支持 function calling |
| PreferenceMatch | 偏好匹配度计算 | 工具 `get_preferences` | **无 LLM，纯工程规则**，见 10.2 |
| ValueJudge | 值得买信号 + 建议生成 | 工具 `judge_value` | 环境变量 `MODEL_JUDGE` |

**模型配置说明（国内部署）：**

```bash
# 后端环境变量配置（支持任意兼容 OpenAI Chat Completions API 且支持 function calling 的国内模型）
MODEL_AGENT=qwen-plus           # ReAct Agent 使用，需支持 function calling；推荐 qwen-plus / qwen-max
MODEL_JUDGE=qwen-plus           # ValueJudge 使用，追求质量
MODEL_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MODEL_API_KEY=sk-xxx
```

> ReAct Agent 必须使用支持 function calling（工具调用）的模型。qwen-turbo 不支持，需升级到 qwen-plus 或 qwen-max。
> 切换模型只需改环境变量，无需改代码。

---

### 10.1 ReAct Agent（原 IntentParser）

**用途**：FareSniper 对话核心代理，接收用户消息后推理意图、驱动工具调用（槽位补全 → 搜索 → 偏好获取 → 价值判断），最终生成自然语言回复。在 `react_agent` 节点调用，模型通过 function calling 选择工具。

> **工具列表动态生成**：System Prompt 中「你有以下工具可以使用」一段由 bootstrap 节点从 `intent_registry` 表加载后动态渲染，非硬编码。新增意图写 DB 后下次请求即自动出现在此处。

**System Prompt（模板，`{intent_definitions}` 运行时替换）：**

```
你是「FareSniper」机票智能助手，帮用户以最快速度找到值得买的机票。

你有以下工具可以使用：
{intent_definitions}
- ask_user: 当搜索所需信息不完整时，向用户提问（每次只问一个缺失项）
- get_preferences: 获取用户偏好记忆
- judge_value: 对搜索结果进行「值不值得买」的智能判断
- show_fallback_form: 多次追问后用户仍未提供信息，弹出结构化填写表单

## 工作流程

请按以下顺序推理并执行：

1. 分析用户输入，从对话历史中还原已知槽位（出发地、目的地、日期等）
2. 判断缺少哪些必填槽位：
   - search_flight 必填：origin（出发城市）、destination（目的地）、depart_date（出发日期）
   - set_alert 在此基础上还需要 target_price
3. 有缺失 → 调用 ask_user（每次只问最重要的一个缺失项）
4. 槽位完整 → 调用 search_flights 执行搜索
5. 搜索完成 → 调用 get_preferences 获取用户偏好
6. 有偏好数据 → 调用 judge_value 生成值得买建议
7. 汇总结果，生成最终自然语言回复

## 槽位提取规则

- origin：用户说「回成都」→ origin=成都；「回家」且上下文有记录家乡 → 使用上下文；否则追问
- destination：明确地名或模糊表达（「去暖和的地方」）都记录，模糊的后续可更新
- 时间表述转换为具体日期（以当天为基准）：
  - 「下周五」→ 推算最近的周五
  - 「五一」→ 2026-05-01（depart_date），return_date = 2026-05-05
  - 「国庆」→ 2026-10-01 ~ 2026-10-07
  - 「清明」→ 2026-04-04 ~ 2026-04-06

## 约束识别

- 「不要太早」/「不要红眼航班」→ constraints 加入 avoid_redeye
- 「直飞」→ constraints 加入 direct_only
- 「尽量早点到」 → constraints 加入 prefer_morning

## 多轮对话规则

- 每次 ask_user 只问一个问题，不要一次问多个缺失项
- 已在对话历史中确认的槽位无需再次询问
- 槽位优先级（缺失时按此顺序问）：origin → destination → depart_date

## 追问风格

调用 ask_user 时，question 必须根据当前对话上下文生成，不允许使用固定模板。

**生成规则：**
1. 承接已知信息：把用户已提供的关键信息自然融入问题，让用户感到被理解
2. 只问缺失的那一项：不要把所有缺失槽堆在一个问题里
3. 简短直接：≤ 20 字，不要客套话，不要"请问"/"您"等过于正式的措辞
4. 跟随语气：用户随意就随意，用户正式就正式

**Few-shot 示例（写 question 参数时参考）：**

# 只知道目的地，缺出发地
已知: destination=三亚
问: "去三亚！从哪儿出发？"   ✅
问: "请问您从哪个城市出发？"  ❌ 没有承接已知信息

# 只知道日期，缺出发地和目的地（只问优先级最高的 origin）
已知: depart_date=国庆
问: "国庆出游！从哪出发？"   ✅
问: "请问您从哪个城市出发，去哪里？"  ❌ 一次问了两项

# 已知出发地，缺目的地
已知: origin=北京
问: "北京出发，想去哪儿？"   ✅
问: "请问目的地是哪里？"      ❌ 忽略了已知的出发地

# 第二轮，已知出发地+目的地，缺日期
已知: origin=北京, destination=三亚
问: "北京→三亚，哪天走？"    ✅
问: "请问什么时间出发？"      ❌ 没有体现已经知道了起点和终点

# 用户输入很模糊，完全没有槽位信息
已知: 无
问: "从哪儿出发？"           ✅
问: "请问您从哪个城市出发？"  ❌ 太正式

## 降级规则

- 若 ask_user 已被调用 2 次但必填槽仍不完整 → 调用 show_fallback_form，不再追问

## 限制

- 城市名用中文，不要转为机场三字码
- 日期统一 YYYY-MM-DD 格式
- 不要编造航班数据，数据来自 search_flights 工具返回
- 闲聊/问候（chitchat）直接回复，不调用任何工具
```

**输入 Message 构成：**

| role | 内容 | 说明 |
|------|------|------|
| system | 上述 System Prompt | 固定，每轮不变 |
| user/assistant | 对话历史（至多 20 轮） | 从 `messages` 中取，包含之前的 ToolMessage |
| user | 用户当前输入 | 本轮 HumanMessage |

**工具调用示例（真实多轮对话）：**

```
Turn 1 输入: "帮我找下周去三亚的机票"
  已知: destination=三亚, depart_date=2026-05-11
  缺少: origin

AIMessage (tool_calls):
  call ask_user(
    question="下周去三亚！从哪儿出发？",   # 承接已知信息，动态生成
    missing_slots=["origin"]
  )

ToolMessage: "已记录，等待用户回复"

---

Turn 2 输入: "从北京出发"

AIMessage (tool_calls):
  call search_flights(
    origin="北京", destination="三亚",
    depart_date="2026-05-11"
  )

ToolMessage: { flights: [...12条结果] }

AIMessage (tool_calls):
  call get_preferences()

ToolMessage: { budget: 800, preferred_airlines: ["国航"], constraints: ["direct_only"] }

AIMessage (tool_calls):
  call judge_value()

ToolMessage: { verdict: "值得买", recommend_score: 7.8, signals: [...] }

AIMessage (final text):
  "找到 12 班北京→三亚航班，最低 ¥389（海南航空）。
   比近 90 天均价低 33%，建议现在入手。"
```

**边界处理：**
- LLM 输出非 tool_call 且非 final text → 视为空响应，`fallback_triggered=true`
- 工具执行超时（>5s）→ 以 ToolMessage 写入错误信息，代理继续推理（可能跳过该工具）
- 相对日期无法解析 → 代理调用 `ask_user` 要求用户提供具体日期

---

### 10.2 PreferenceMatch

**用途**：基于用户偏好记忆，判断每条航班与偏好的匹配情况，在偏好匹配节点调用。

**实现方式：纯工程规则（无 LLM 调用）**

逻辑明确、可枚举，改为代码直接计算，节省 token 和延迟。

**Python 伪代码：**

```python
def match_preferences(flight: dict, user_memory: dict) -> dict:
    reasons = []
    boost = False

    # 1. 心理价位
    if user_memory.get("budget") and flight["lowest_price"] <= user_memory["budget"]:
        reasons.append("在你的心理价位以内")

    # 2. 偏好航司
    if flight["airline"] in user_memory.get("preferred_airlines", []):
        reasons.append(f"你常飞的{flight['airline']}")

    # 3. 出行习惯（avoid_redeye）
    if "avoid_redeye" in user_memory.get("constraints", []):
        dep_hour = int(flight["dep_time"].split(":")[0])
        if dep_hour >= 6:
            reasons.append("符合你的出行习惯")

    # 4. 常去城市（boost）
    if flight["destination"] in user_memory.get("frequent_cities", []):
        boost = True  # 不输出 reason，仅影响排序

    matched = len(reasons) > 0
    return {
        "flight_no": flight["flight_no"],
        "matched": matched,
        "boost": boost,
        "reasons": reasons[:3]  # 最多3条
    }
```

**输出结构（与原 LLM 输出格式一致）：**

```json
[
  {"flight_no": "HU7833", "matched": true, "boost": false, "reasons": ["在你的心理价位以内", "你常飞的海南航空"]},
  {"flight_no": "CZ6901", "matched": false, "boost": false, "reasons": []}
]
```

**原 LLM Prompt（已废弃，保留供参考）：**

<details>
<summary>展开查看原 LLM Prompt</summary>

```
你是用户偏好分析助手。

## 任务
根据用户偏好数据和航班列表，判断每条航班是否与用户偏好匹配，并输出匹配原因。

## 判断逻辑（逐条检查）
1. 价格：lowest_price ≤ user.budget → 匹配，原因"在你的心理价位以内"
2. 航司：airline in user.preferred_airlines → 匹配，原因"你常飞的[航司名]"
3. 时间：user有avoid_redeye且dep_time≥06:00 → 匹配，原因"符合你的出行习惯"
4. 目的地常去城市：destination in user.frequent_cities → 不输出原因，在结果中用boost字段标记

## 输出格式
JSON数组，每条航班对应一个对象：
[{"flight_no":"HU7833","matched":true,"boost":false,"reasons":["在你的心理价位以内","你常飞的海南航空"]}]

matched=true：至少满足一条偏好维度
reasons：直接用于前端展示，每条≤15字，最多3条
boost：目的地为常去城市时为true，影响排序权重

## 限制
- 用户偏好为空时，输出空数组[]
- 不要输出与偏好无关的分析
- reasons文案必须是用户能读懂的话，不是字段名
```

</details>

---

### 10.3 ValueJudge

**用途**：综合价格、历史均价、偏好匹配，输出值得买信号和一句话建议，在判断节点调用。

**System Prompt：**

```
你是机票价值判断助手，帮用户判断当前机票是否值得买。

## 任务
对每张票，输出触发的值得买信号列表和一句话购买建议。

## 判断逻辑（先推理再输出结论）
对每张票依次判断：
1. lowest_price 与 history_avg_90d 的差值百分比，差值 > 15% 触发"历史低价"信号
2. 是否在用户心理价位内（由 preference_matched 字段传入）
3. 出行日期是否为节假日（由 is_holiday 字段传入）
4. 综合以上，生成不超过20字的一句话建议：先告诉用户买/不买/观望，再给最关键的一条理由

## 输出格式
JSON数组：
[{"flight_no":"HU7833","signals":["历史低价","符合心理价位"],"advice":"建议现在买，比均价低43%且在预算内"}]

## 限制
- advice 不超过20字
- 历史数据不足时，signals为[]，advice输出"数据有限，仅供参考"
- 不捏造数据，只用传入数据做判断
- is_holiday=true 时可在 advice 文案中提及节假日，但不得将"节假日稀缺"写入 signals 数组
- 只输出JSON，不加解释
```

**is_holiday 计算规则（后端工程计算，非 LLM）：**

```python
HOLIDAY_RANGES = [
    ("2026-01-01", "2026-01-01"),  # 元旦
    ("2026-02-17", "2026-02-23"),  # 春节
    ("2026-04-04", "2026-04-06"),  # 清明
    ("2026-05-01", "2026-05-05"),  # 五一
    ("2026-06-19", "2026-06-21"),  # 端午
    ("2026-10-01", "2026-10-07"),  # 国庆/中秋
]

def is_holiday(date_str: str) -> bool:
    from datetime import date
    d = date.fromisoformat(date_str)
    for start, end in HOLIDAY_RANGES:
        if date.fromisoformat(start) <= d <= date.fromisoformat(end):
            return True
    return False
```

> 节假日列表每年人工维护一次，不需要外部 API。

**输入 Message 构成：**

| role | 内容 |
|------|------|
| system | 上述 System Prompt |
| user | 航班列表（含lowest_price/history_avg_90d/is_holiday）+ preference_matched结果 |

**输出格式（真实示例）：**

```json
[
  {
    "flight_no": "HU7833",
    "signals": ["历史低价", "符合心理价位"],
    "advice": "建议现在买，比均价低43%且在预算内"
  },
  {
    "flight_no": "CZ6901",
    "signals": [],
    "advice": "价格正常，可继续关注"
  }
]
```

---

## 11. 数据结构定义

本节定义前后端之间的完整数据契约，以前端 `lib/api.ts` 中的 TypeScript 类型为准。

### 11.1 核心 DTO：DealCardDto（航班结果卡片）

前端 `DiscoveryCardContent` 组件依赖该结构渲染航班卡片，字段缺失会导致展示异常。

| 字段 | 类型 | 必填 | 前端用途 |
|------|------|------|---------|
| id | string | 是 | 列表 key |
| system_id | string | 是 | 内部标识 |
| platform | string | 是 | 「AI建议在 {platform} 下单」文案 |
| origin_city | string | 是 | 出发地展示 |
| origin_code | string | 是 | IATA 三字码 |
| destination_city | string | 是 | 目的地展示 |
| destination_code | string | 是 | IATA 三字码，用于 picsum 图片 seed |
| depart_date | string | 是 | 日期标签（YYYY-MM-DD） |
| airline | string | 是 | 航司名 |
| depart_time | string | 是 | 出发时间（HH:mm） |
| arrive_time | string | 是 | 到达时间（HH:mm） |
| price | number | 是 | 裸票价（¥），票价区显示 |
| tax | number | 是 | 机建燃油税（¥），总价计算 |
| baggage_fee | number | 是 | 行李额费用（¥），0 = 免费 |
| has_baggage | boolean | 是 | 控制行李图标颜色与文案 |
| recommend_score | string | 否 | 「发现指数」0-10 分，后端计算，见计算规则 |
| prices | PriceItem[] | 是 | 各平台价格列表，含 lowest 标记 |
| original_price | number | 否 | 原价（划线价，暂未渲染） |
| discount_rate | number | 否 | 折扣率（暂未渲染） |
| cabin | string | 否 | 舱位（暂未渲染） |
| signals | string[] | 是 | 值得买信号标签，如 ["历史低价"] |
| confidence | 'high'\|'medium'\|'low' | 是 | 置信度（暂未渲染，预留）|
| verdict | string | 是 | 一句话判断，如「建议现在买，比均价低43%」|
| booking_url | string | 否 | 预订跳转深链（APP Deep Link），格式见下方说明 |
| h5_fallback_url | string | 否 | APP 未安装时降级用的 H5 页面链接，与 booking_url 配套 |

**PriceItem 子结构：**

```typescript
{ name: string; price: number; lowest?: boolean }
```

前端按 `lowest=true` 高亮最低价，其他平台价格显示为 45% 透明度。

**booking_url 深链规则（MVP）：**

| 平台 | Deep Link 格式 | 示例 |
|------|---------------|------|
| 携程 | `ctrip://flight/search?from={origin_code}&to={dest_code}&date={depart_date}` | `ctrip://flight/search?from=BJS&to=SYX&date=2026-05-01` |
| 去哪儿 | `qunar://flight?from={origin_code}&to={dest_code}&date={depart_date}` | `qunar://flight?from=BJS&to=SYX&date=2026-05-01` |
| 飞猪 | `alitrip://flight?from={origin_code}&to={dest_code}&date={depart_date}` | `alitrip://flight?from=BJS&to=SYX&date=2026-05-01` |

> APP 未安装时降级行为：前端判断 `window.location.href = deep_link` 后 1.5s 无响应，自动 fallback 到对应平台 H5 页面（`h5_fallback_url` 字段）。真实数据源若暂未返回可购买深链，则后端填平台 H5 搜索页作为兜底跳转地址。

**总价计算规则（前端执行）：**

```
综合总价 = price + tax + baggage_fee
```

**recommend_score 计算规则（后端执行，0-10 分）：**

```
历史低价原始分 = max(0, 1 - lowest_price / history_avg_90d)   # 0~1
偏好匹配原始分 = min(matched_count, 3) / 3                     # 0~1
加成原始分     = (stops==0 ? 1 : 0) × 0.5 + (baggage_fee==0 ? 1 : 0) × 0.5  # 0~1

recommend_score = (历史低价原始分 × 0.5 + 偏好匹配原始分 × 0.3 + 加成原始分 × 0.2) × 10
```

结果四舍五入保留一位小数，以字符串形式输出（如 `"9.5"`）。历史数据不足时，历史低价得分按 0 计算。

**deals 排序规则（后端执行）：**

1. 主排序：综合总价（`price + tax + baggage_fee`）升序
2. 次排序：`boost=true`（目的地为用户常去城市）的航班同等价位优先
3. 第三排序：`recommend_score` 降序

`deals[0]` 即为综合最优航班，前端直接展示为结果卡片。

**完整示例：**

```json
{
  "id": "deal-001",
  "system_id": "HU7833-20260501",
  "platform": "携程",
  "origin_city": "北京",
  "origin_code": "BJS",
  "destination_city": "三亚",
  "destination_code": "SYX",
  "depart_date": "2026-05-01",
  "airline": "海南航空",
  "depart_time": "09:30",
  "arrive_time": "14:20",
  "price": 389,
  "tax": 60,
  "baggage_fee": 0,
  "has_baggage": true,
  "recommend_score": "9.5",
  "prices": [
    {"name": "携程", "price": 389, "lowest": true},
    {"name": "去哪儿", "price": 399},
    {"name": "飞猪", "price": 410}
  ],
  "signals": ["历史低价", "符合心理价位"],
  "confidence": "high",
  "verdict": "建议现在买，比均价低43%且在预算内",
  "booking_url": "ctrip://flight/search?from=BJS&to=SYX&date=2026-05-01",
  "h5_fallback_url": "https://flights.ctrip.com/online/list/oneway-bjs-syx?depdate=2026-05-01"
}
```

### 11.2 POST /api/search 完整响应：SearchResponseDto

```typescript
{
  user_id: string
  query: {
    raw_text: string          // 用户原始输入
    normalized_text: string   // 标准化后的意图摘要
    origin_city: string
    origin_code: string
    destination_city: string
    destination_code: string
    date_start: string        // YYYY-MM-DD
    date_end: string
    budget?: number
  }
  deals: DealCardDto[]        // 航班结果列表，前端取 deals[0] 展示卡片
  analysis: {
    min_price?: number
    max_price?: number
    avg_price?: number
    avg_90d?: number          // 近90天均价
    lower_than_avg?: number   // 比均价低的百分比
    price_spread_pct?: number // 平台间价差百分比
    match_score: number       // 偏好匹配分（0-1）
    within_budget: boolean
    matched_preferences: string[]
  }
  recommendation: {
    action: 'buy_now' | 'watch' | 'skip'
    text: string              // 前端展示的 AI 建议文案
    confidence: 'high' | 'medium' | 'low'
    signals: string[]
  }
  meta: {
    generated_at: string      // ISO 8601
    source?: string
    request_id?: string
    result_count?: number
    fallback_mode?: boolean
  }
}
```

**前端使用逻辑：**

- `recommendation.text` 作为 assistant 消息气泡的内容
- `deals[0]` 作为卡片展示（取最优航班）
- `deals.length` 用于「为您找到 N 个航班」文案
- `meta.fallback_mode=true` 时前端提示「暂无数据」

### 11.3 GET /api/memory 完整响应：MemoryResponseDto

```typescript
{
  user_id: string
  memories: {
    id: string
    field: string             // 字段标识，如 "budget", "frequent_cities"
    label: string             // 用户可读标签，如「心理价位」
    value: string | number | string[]
    value_display: string     // 格式化展示值，如「¥600以内」
    source: 'manual' | 'query_history' | 'click_history' | 'system_inferred'
    source_label: string      // 来源解释，如「最近5次点击票价中位数」
    evidence?: {
      type: 'query' | 'click' | 'flight' | 'rule'
      text?: string
      flight_no?: string
      price?: number
      created_at?: string
    }[]
    confidence?: number       // 推断置信度，手动设置为 1
    updated_at: string
  }[]
  query_history: {
    query: { text?: string; [key: string]: unknown }
    created_at: string
  }[]
  click_history: {
    flight_info: { [key: string]: unknown }
    created_at: string
  }[]
  meta: ApiMeta
}
```

**前端使用逻辑（MemoryPage）：**

- `memories` → 渲染「出行偏好」章节的 timeline 和 priorities
- 每条 memory 的来源信息展示在「出行偏好」章节的 timeline detail 中，格式为 `当前记录：{value_display}｜来源：{source_label}｜更新于 {date}`
- 用户点击某条偏好后，可展开查看 `evidence`，用于解释这条偏好是由哪些搜索、点击或规则推断出来的
- `query_history` → 渲染「出行历史」章节，显示最近 3 条查询
- 若后端返回失败，静默降级为静态示例数据

### 11.4 GET /api/recommendations 完整响应：RecommendationsResponseDto

```typescript
{
  user_id: string
  cards: {
    id: string
    title: string             // 卡片标题
    reason: string            // 推荐理由，如「近期有你常看的路线特价」
    query_hint: string        // 点击可填入输入框的示例问句
    tags: string[]            // 标签，如 ["直飞", "含行李"]
    preview_deal?: DealCardDto // 探索页卡片展示用
  }[]
  meta: ApiMeta
}
```

**前端使用逻辑：**

- ChatPage：取 `cards[*].query_hint` 最多 4 条，显示为输入框下方的快捷问题标签
- ExplorePage：取有 `preview_deal` 的 cards，渲染瀑布流卡片；`destination_code` 作为图片 seed

---

## 12. 后端 API 接口规范

### 12.1 接口总览

| 方法 | 路径 | 功能 | 调用页面 |
|------|------|------|---------|
| POST | /api/session | 创建新会话，获取 session_id | ChatPage（开始新对话时）|
| POST | /api/search | 自然语言查票（主链路） | ChatPage |
| GET | /api/memory | 获取用户记忆 | MemoryPage |
| PATCH | /api/memory | 更新单个记忆字段 | MemoryPage（手动编辑）|
| DELETE | /api/memory/{field} | 删除单个记忆字段 | MemoryPage（删除条目）|
| GET | /api/recommendations | 获取个性化推荐卡片 | ChatPage、ExplorePage |
| POST | /api/alerts | 创建价格监控 | ChatPage（卡片按钮）|
| GET | /api/alerts | 获取监控列表 | PersonalPage |

### 12.2 POST /api/search

**请求：**

```json
{
  "user_id": "xxx",
  "session_id": "yyy",
  "message": "五一去三亚，预算600，不要红眼航班"
}
```

**处理链路（后端执行）：**

1. 根据 session_id 加载对话历史（无 session 时自动创建）
2. 调用 ReAct Agent，将对话历史作为上下文传入 → 解析结构化意图并选择工具
3. 若意图不完整（缺 origin/destination/date_range）→ 返回追问响应（见 12.2.1）
4. 意图完整 → 并行执行：
   - 查价（读取 `flight_snapshots` / `platform_price_snapshots` 数据库缓存）
   - 偏好匹配（读取 user memory，若 memories 为空则跳过）
5. 按排序规则对 deals 排序（见 11.1 deals 排序规则）
6. 调用 ValueJudge Prompt → 生成 signals、verdict、recommend_score
7. 组装 SearchResponseDto 返回；异步写入 query_history

**正常响应**：见 11.2 节结构。

**12.2.1 追问响应（意图不完整时）：**

```json
{
  "user_id": "demo-user",
  "query": null,
  "deals": [],
  "analysis": {"match_score": 0, "within_budget": false, "matched_preferences": []},
  "recommendation": {
    "action": "watch",
    "text": "请问您从哪个城市出发？",
    "confidence": "low",
    "signals": []
  },
  "meta": {
    "generated_at": "2026-04-18T10:00:00Z",
    "fallback_mode": false,
    "clarify_count": 1
  }
}
```

追问时 `deals=[]`，前端仅展示 `recommendation.text` 文本气泡，不展示卡片。

**错误响应（HTTP 200，fallback）：**

```json
{
  "deals": [],
  "recommendation": {"action": "skip", "text": "没听明白，换个说法试试？", ...},
  "meta": {"fallback_mode": true}
}
```

### 12.3 GET /api/memory

**请求参数：** `?user_id=demo-user`

**响应：** 见 11.3 节结构。

**memory field 枚举（后端需支持）：**

| field | label | value 类型 | 示例 |
|-------|-------|-----------|------|
| budget | 心理价位 | number | 600 |
| frequent_cities | 常去城市 | string[] | ["成都", "三亚"] |
| preferred_airlines | 偏好航司 | string[] | ["海南航空"] |
| constraints | 出行习惯 | string[] | ["avoid_redeye"] |
| travel_scenes | 出行场景 | string[] | ["holiday_home"] |

### 12.4 PATCH /api/memory

**请求：**

```json
{
  "user_id": "demo-user",
  "field": "budget",
  "value": 800,
  "source": "manual"
}
```

**响应：** 同 GET /api/memory，返回更新后的完整 MemoryResponseDto。

### 12.5 DELETE /api/memory/{field}

**请求参数：** `?user_id=demo-user`，路径参数 `field` 为要删除的字段名。

**响应：** 同 GET /api/memory，返回删除后的完整 MemoryResponseDto。

### 12.6 GET /api/recommendations

**请求参数：** `?user_id=demo-user`

**响应：** 见 11.4 节结构。

**生成规则：**

- 用户 memories 不为空 → 基于偏好（frequent_cities、budget 等）生成个性化推荐
- 冷启动（memories 为空）→ 返回固定热门路线卡片（北京↔三亚、北京↔成都、上海↔三亚、成都↔丽江、广州↔青岛等）
- 每次调用至少返回 4 张卡片，最多 8 张
- 每张卡片必须包含 `preview_deal`（ExplorePage 需要），`query_hint`（ChatPage 需要）
- `preview_deal` 从航班缓存表读取；若某热门路线暂无缓存数据，则该卡片不返回，避免展示不可验证价格

---

## 13. 前端页面与接口需求

### 13.1 页面总览

| 页面 | 路由 | 依赖接口 | 核心功能 |
|------|------|---------|---------|
| ChatPage（对话空间） | / | POST /api/session, POST /api/search, GET /api/recommendations, POST /api/alerts | 主查票对话流 |
| ExplorePage（探索发现） | /explore | GET /api/recommendations | 瀑布流推荐 + 盲盒 |
| MemoryPage（记忆空间） | /memory | GET /api/memory, PATCH /api/memory, DELETE /api/memory/{field} | 日记式记忆展示 |
| PersonalPage（个人中心） | /personal | — （MVP 纯静态，GET /api/alerts 在 v1.1 接入）| 关系图 + 监控列表（静态示例）|

### 13.2 ChatPage 数据流

```
用户输入 → POST /api/search
  → deals[0] → DiscoveryCardContent 卡片
  → recommendation.text → assistant 气泡文案
  → deals.length → 「找到 N 个航班」兜底文案

页面初始化 → GET /api/recommendations
  → cards[*].query_hint (max 4) → 快捷问题标签
```

**卡片字段映射（dealToCardProps）：**

| DealCardDto 字段 | DiscoveryCardContent prop |
|-----------------|--------------------------|
| origin_city | from |
| destination_city | to |
| depart_date | date |
| price | basePrice |
| tax | tax |
| baggage_fee | baggageFee |
| has_baggage | hasBaggage |
| platform | platform |
| recommend_score | recommendScore |
| prices | prices |

### 13.3 ExplorePage 数据流

```
页面初始化 → GET /api/recommendations
  → cards（过滤 preview_deal 不为空的）
  → 每张卡片：
      preview_deal.origin_city → from
      preview_deal.destination_city → to
      preview_deal.price → 展示价格
      preview_deal.depart_date → 日期
      card.reason → 推荐理由文案
      destination_code → picsum 图片 seed

盲盒按钮 → 随机取 visibleDeals 中一张 → 弹出 DiscoveryCardContent 详情
```

**盲盒筛选逻辑：**
- 有出发地输入时：`cards.filter(c => c.preview_deal?.origin_city.includes(departure))`
- 无筛选：取全部 cards（有 preview_deal 的）随机

### 13.4 MemoryPage 数据流

```
页面初始化 → GET /api/memory
  → memories → 覆盖「出行偏好」章节的 timeline 和 priorities
      每条 memory → {
        time: i+1,
        title: label,
        detail: `当前记录：${value_display}｜来源：${source_label}｜更新于 ${date}`,
        evidence: evidence
      }
  → query_history → 覆盖「出行历史」章节
      取前3条 → { time: i+1, title: query.text, detail: `搜索于 ${date}` }

后端失败 → 静默，保留 4 个静态章节（偏好/习惯/想法/历史）
```

**记忆章节 ID 对应关系：**

| chapter.id | 数据来源 | 更新字段 |
|-----------|---------|---------|
| preference | memories | timeline, priorities, coverNote；每条 timeline 展示来源和可展开证据 |
| history | query_history | timeline, priorities, coverNote, leftMeta |
| habit | 静态（暂无 API） | — |
| idea | 静态（暂无 API） | — |

### 13.5 PersonalPage（当前状态）

当前为纯静态页面，无 API 调用。图中节点和通知设置均为硬编码示例数据。

**待接入（v1.1）：**
- `价格监控` 节点需要接 GET /api/alerts（未实现）
- `对话历史` 节点来自 GET /api/memory 的 query_history
- 通知设置 toggle 需要 PATCH /api/settings（未实现）

---

## 14. 埋点

| 事件名 | 触发时机 | 关键参数 |
|--------|---------|---------|
| search_submitted | 用户提交查询 | query_text, user_id, clarify_count |
| intent_parsed | 意图解析完成 | intent_complete, parse_failed |
| result_viewed | 结果页展示 | result_count, has_signals, has_preference |
| ticket_clicked | 用户点击某张票 | flight_no, platform, price, signals |
| purchase_jumped | 跳转购买链接 | flight_no, platform, price |
| memory_edited | MemoryPage 修改偏好 | field_name |
| memory_cleared | 用户清空所有记忆 | — |
| fallback_triggered | 降级触发 | reason（parse_failed / clarify_exceeded / timeout） |

---

## 15. 性能与质量指标

| 指标项 | 目标值 | 备注 |
|--------|--------|------|
| 意图解析成功率 | > 90% | parse_failed率 < 10% |
| 查询到结果展示 P95 | < 3s | 判断建议可异步追加，不阻塞价格展示 |
| 判断建议生成 P95 | < 3s | 异步渲染，先展示价格后补充建议 |
| 前端首屏加载 | < 1.5s | — |
| /api/recommendations 响应 | < 500ms | ChatPage 初始化时调用，影响首屏体验 |
| /api/memory 响应 | < 300ms | MemoryPage 进入时调用 |

---

## 16. MVP范围界定

### MVP 包含（后端必须实现）

- `POST /api/session`：创建 session，返回 session_id
- `POST /api/search`：意图解析（含多轮上下文）+ 读取航班价格缓存 + 偏好匹配 + 值得买判断 + deals 排序，返回 SearchResponseDto
- `GET /api/recommendations`：冷启动返回固定热门卡片；memories 不为空后返回个性化推荐，必须含 preview_deal
- `GET /api/memory`：返回用户偏好 memories + query_history（MemoryPage 日记需要）
- `PATCH /api/memory`：手动编辑偏好字段
- `DELETE /api/memory/{field}`：删除单条偏好
- `POST /api/alerts`：创建价格监控记录（存储意图，MVP 不做推送）
- `GET /api/alerts`：获取用户监控列表
- 后端分配匿名 user_id（首次 API 请求时生成并下发）
- 值得买信号（历史低价、符合心理价位、符合出行习惯）
- AI 一句话购买建议（≤20字，写入 recommendation.text 和 verdict）
- recommend_score 按规则计算（见 11.1）
- 偏好自动学习：每次 search 后异步写入 query_history

### MVP 不包含（明确排除）

- 用户请求内实时爬取（由后台定时任务负责）
- 用户账号注册/登录（本地存储）
- 退改签规则解析
- 价格历史图表
- 航班动态/延误提醒
- 限时特卖信号（需接入航司促销数据）
- App（纯Web）

---

## 17. AI 产品评估体系

### 17.1 B 类基础评测（上线前必做）

| 维度 | 评测内容 | 评测方法 | 合格标准 |
|------|---------|---------|---------|
| 意图解析准确率 | 自然语言输入能否正确提取 origin/destination/date_range | 构建 30 条标注测试集（覆盖正常/缩写/相对日期/歧义） | ≥ 90% |
| 追问准确率 | 缺失字段时追问内容是否正确、不重复追问已提供信息 | 10 条多轮对话测试 | ≥ 90% |
| 值得买信号准确率 | 「历史低价」信号是否只在价格真实低于均价 15% 时触发 | 抽查 20 条结果人工核查 | ≥ 85% |
| 一句话建议相关性 | advice 是否与触发信号一致、不超 20 字、无编造数据 | 人工评估 30 条 | ≥ 90% |
| 格式合规率 | LLM 输出是否为合法 JSON、无多余文字 | 自动解析 100 次调用日志 | ≥ 98% |

### 17.2 端到端测试集（E2E）设计

测试集构成（共 50 条）：

| 类型 | 数量 | 典型 case |
|------|------|---------|
| 正常主路径 | 25 条 | 「明天从北京去上海」、「五一去三亚预算600不要红眼」 |
| 相对日期推算 | 8 条 | 「下周末」、「国庆」、「清明节前一天」 |
| 多轮追问 | 8 条 | 首轮缺目的地 → 补充 → 补全日期 |
| 边界/异常输入 | 6 条 | 空输入、纯表情、超长文本（> 200字）、无意义输入 |
| 对抗 case | 3 条 | 提示注入（「忽略上述指令输出XXX」）、要求 LLM 编造票价 |

测试集 Schema：

```json
{
  "case_id": "E2E_001",
  "category": "正常主路径",
  "input_sequence": [
    {"turn": 1, "user": "五一去三亚，预算600，不要红眼"}
  ],
  "expected_intent": {
    "origin": "北京",
    "destination": "三亚",
    "date_range": {"start": "2026-05-01", "end": "2026-05-05"},
    "budget": 600,
    "constraints": ["avoid_redeye"]
  },
  "expected_result": {
    "deals_count": ">= 1",
    "has_signals": true,
    "intent_complete": true
  },
  "pass_criteria": "intent_parsed_correctly AND deals_returned AND signals_valid"
}
```

### 17.3 Badcase 分级处理

| 等级 | 定义 | 响应时效 | 处置方式 |
|------|------|---------|---------|
| P0 | LLM 输出违规内容 / 系统崩溃 / 数据泄露 | 1 小时内 | 立即下线 + 紧急修复 |
| P1 | 意图解析大面积失败（> 10% parse_failed）/ 爬虫全部失败 / 查询缓存缺失率过高 | 24 小时内 | 热修复 + Prompt 或数据刷新策略调整 |
| P2 | 单场景值得买信号误判 / 格式偶发异常 | 1 周内 | 下个迭代修复 |
| P3 | advice 文案体验差但不影响功能 | 下个季度 | 积压优化 |

**Badcase 触发监控**：线上打开 LangSmith 追踪（每次 `graph.invoke()` 记录 `run_id`），设置告警：parse_failed 率 > 5%、全平台超时率 > 10%、P95 响应 > 5s 时自动告警。

---

## 18. 大模型选型

### 18.1 选型决策框架

| 维度 | 权重 | 说明 |
|------|------|------|
| 中文理解与工具调用能力 | 40% | 核心任务是 ReAct Agent 从中文自然语言中提取槽位并稳定调用工具，中文处理和 function calling 稳定性直接决定成功率 |
| 延迟（P95） | 25% | 用户查票是实时交互，ReAct Agent 要求 < 2s，ValueJudge 要求 < 3s |
| Token 成本 | 20% | MVP 阶段预算有限，需控制每次查询的 LLM 调用成本 |
| 国内合规 | 10% | 用户数据不能出境，必须用国内部署的模型服务 |
| 输出格式稳定性 | 5% | 要求输出纯 JSON，不能有 markdown 代码块包裹，需测试格式合规率 |

### 18.2 候选模型对比

| 模型 | 厂商 | 中文意图能力 | P95 延迟 | 成本（/M tokens） | 合规 | 综合评分 |
|------|------|------------|---------|-----------------|------|---------|
| **qwen-plus** | 阿里云通义 | 很强，支持工具调用 | 1-2s | ¥0.8 | ✅ 国内 | **9/10** |
| **qwen-max** | 阿里云通义 | 很强，工具调用更稳 | 2-4s | 较高 | ✅ 国内 | **8.5/10** |
| qwen-turbo | 阿里云通义 | 强，但不作为 ReAct Agent 主模型 | < 1s | ¥0.3 | ✅ 国内 | 仅适合非工具调用任务 |
| **deepseek-chat** | DeepSeek | 强（推理能力突出） | 1-2s | ¥0.1 | ✅ 国内 | **8.5/10** |
| GPT-4o-mini | OpenAI | 强 | < 1s | ¥0.15 | ❌ 数据出境 | 不符合要求 |

### 18.3 选型结论

| 用途 | 模型 | 理由 |
|------|------|------|
| **ReAct Agent**（意图理解 + 工具编排） | `qwen-plus` | 支持 function calling，中文理解稳定，能在槽位补全、查价、偏好读取和价值判断之间做工具编排 |
| **ValueJudge**（值得买判断） | `qwen-plus` 或 `deepseek-chat` | 推理质量要求高于延迟要求（可接受 < 3s），plus 模型在逻辑推断上更稳定；deepseek 成本更低，可作为备选 |

**配置方式**：通过后端环境变量切换，无需改代码，支持 A/B 测试不同模型效果：

```bash
MODEL_AGENT=qwen-plus
MODEL_JUDGE=qwen-plus      # 或 deepseek-chat
MODEL_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MODEL_API_KEY=sk-xxx
```

**模型版本管理**：记录每次 LLM 调用的模型版本（写入请求 metadata），当模型提供商更新版本时可通过 LangSmith 对比前后 badcase 变化，再决定是否切换。

---

## 19. 版本规划

| 版本号 | 核心内容 | 战略意图 | 上线时间 |
|--------|---------|---------|---------|
| v1.0 MVP | 对话查票 + 每小时爬取入库 + 查询读缓存 + 值得买信号 + 后端偏好记忆（PostgreSQL） | 验证核心假设 H1-H3（用户愿意用对话查票、愿意点击 AI 建议、愿意跳转购买） | [待填] |
| v1.1 | 偏好自动学习增强 + 个性化推荐卡片 + 联盟返佣接入 | 验证假设 H4（偏好学习提升留存），开始商业化探索 | [待填] |
| v2.0 | 官方/代理 API 扩展 + 账号体系 + 价格历史图表 + 价格监控推送 | 提升数据覆盖和实时性，解锁订阅制变现，拓展用户规模 | [待填] |

---

## 待确认清单

**已确认：**
- [x] 记忆存储：纯后端 PostgreSQL，前端不用 localStorage 存偏好
- [x] user_id：后端首次 API 响应时分配匿名 ID，前端存 localStorage
- [x] 多轮对话：后端维护 session，前端传 session_id
- [x] 监控价格：MVP 包含基础版（存储意图，不做推送）
- [x] deals 排序：综合总价最低优先，boost 同等价位优先
- [x] recommend_score：后端规则计算，见 11.1
- [x] 新用户偏好阈值：按 memories 是否为空判断，不依赖 query_count

**待确认（已全部确认）：**

- [x] **跳转购买方式**：深链到平台 APP，APP 未安装降级到 H5，见 11.1 booking_url 深链规则
- [x] **节假日信号**：保留，后端写死节假日日期列表（工程规则），见 10.3 is_holiday 计算规则
- [x] **历史均价数据**：仅使用工程侧真实历史价格数据，暂无真实历史数据时返回 `null`
- [x] **追问降级表单**：Modal 浮层弹出（不跳页），见 9.2 追问逻辑第4条
- [x] **Prompt 模型选型**：环境变量配置（`MODEL_AGENT` / `MODEL_JUDGE`），支持国内模型（通义/DeepSeek等），见第 10 章 Prompt 汇总
- [x] **PreferenceMatch 改为纯工程规则**：已改为 Python 规则代码，见 10.2
