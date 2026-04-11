# 特价机票发现平台 - 技术架构与执行步骤

**版本：** v2.1
**日期：** 2026-04-11
**配套文档：** `PRD.md`

> **v2.1 变更：** 在 v2.0 完整架构基础上，增加「分阶段交付」章节，按 MVP → 真实数据 → 精细化 三阶段推进，每阶段都可以独立上线验证。
>
> **v2.0 架构设计是终态目标，阶段一/二会做必要的简化和替代，避免一步到位。**

---

## 分阶段交付路线图（最重要，先看这个）

**整体节奏：**
```
阶段一 (MVP)           阶段二 (真实数据)         阶段三 (精细化)
  前端页面            后端+数据源接入           完整 AgentScope 架构
  本地 mock 交互       部署上线                  优化+一键部署
  Vercel 可演示        能真实出结果              可交付可维护
```

**每阶段交付条件：**

| 阶段 | 完成标志 | 时间预估 | 架构复杂度 |
|------|---------|---------|-----------|
| 阶段一 | 前端三屏可点击、Vercel 可访问 | 1天 | ⭐ |
| 阶段二 | 真实携程数据能跑通并部署 | 2-3 天 | ⭐⭐ |
| 阶段三 | 完整 AgentScope + Plan-and-Execute + 两层记忆 | 3-5 天 | ⭐⭐⭐⭐⭐ |

---

### 阶段一：MVP 前端页面部署（Day 1）

**目标：** 让三屏流程能在浏览器里跑通，可分享 URL 给用户看产品故事。

**做什么：**

1. **先确定页面布局（UI 优先）**
   - 首页：对话输入框 + 热门低价卡片 + 基于记忆的推荐卡片
   - 结果页：结果卡片 + AI 建议 + 值得买信号
   - 个人中心：偏好列表（可编辑/删除）

2. **再跑通本地交互（纯前端模拟）**
   - 所有数据都写死在前端 `mocks/` 目录下的 JSON
   - 对话输入 → 前端做简单关键词匹配 → 跳转结果页
   - "编辑偏好" → 存在 `localStorage`，刷新不丢
   - **不需要后端，不需要数据库，不需要 LLM**

3. **部署到 Vercel**
   - `vercel --prod` 一键上线
   - 拿到可分享 URL

**技术栈（阶段一）：**
- Next.js 14 + TypeScript + Tailwind + shadcn/ui
- 状态：`useState` + `localStorage`
- 假数据：写死在 `frontend/mocks/*.json`

**不做什么：**
- ❌ Python 后端
- ❌ PostgreSQL / Redis
- ❌ AgentScope
- ❌ flights_monitor
- ❌ LLM 调用

**阶段一交付物：**
- 一个可点击的 Next.js demo
- Vercel URL
- 产品故事完整呈现（找票→判断→记忆）

---

### 阶段二：真实数据上线并部署（Day 2-3）

**目标：** 把前端对接到真实的携程数据，让"AI 推荐"不再是假的。

**做什么：**

1. **最小后端（不用 AgentScope，先用 FastAPI 裸写）**
   - FastAPI 单文件就够，`backend/main.py`
   - 3 个路由：`/search`、`/memory`、`/recommendations`
   - **不用复杂的 Agent 框架**，后端内部流程直接写成 Python 函数链

2. **接入 flights_monitor（核心）**
   - `backend/data_sources/ctrip_source.py` 包一层
   - 同步 Selenium 用 `asyncio.run_in_executor` 异步化
   - 热门航线预热：启动时跑一次，结果缓存

3. **最小 LLM 调用（一个函数，不做 Agent）**
   - `backend/llm.py` 一个文件
   - 两个函数：`parse_intent(text)`、`generate_recommendation(flights, preferences)`
   - 先接 1 家模型（推荐 DeepSeek，便宜快）

4. **最小记忆（JSON 文件先顶着）**
   - `backend/memory.json` 存用户偏好
   - **还没上 PostgreSQL/Redis**
   - 能读能写能展示就行

5. **部署**
   - 前端：Vercel
   - 后端：Railway / Render / 自己服务器（任选）
   - flights_monitor Selenium 需要 Chrome → 选支持 Chrome 的托管方

**技术栈（阶段二）：**
- 前端：不变（Next.js）
- 后端：**FastAPI + flights_monitor + DeepSeek API + JSON 文件**
- 数据库：暂无（JSON 文件代替）
- Agent 框架：暂无（纯 Python 函数）

**阶段二不做什么：**
- ❌ AgentScope（先用普通 Python）
- ❌ Plan-and-Execute 架构（先串行）
- ❌ PostgreSQL / Redis（JSON 文件先顶）
- ❌ LazyAgentRegistry（不需要插件化）
- ❌ 熔断器、异步总结（先不要）

**阶段二交付物：**
- 真实携程数据能返回
- AI 推荐是真的 LLM 生成的
- 前后端都在线上，可分享真实体验

---

### 阶段三：架构精细化 + 一键部署（Day 4-8）

**目标：** 把阶段二的"能跑"升级为"可维护、可扩展、可交付"的完整架构。

**做什么（严格按顺序）：**

1. **先接数据库（Day 4）**
   - 从 JSON 文件迁移到 **PostgreSQL**（`docker-compose.yml` 启）
   - 建表：`preferences` / `query_history` / `click_history` / `chat_history`
   - SQLAlchemy 2.0 async + Alembic 迁移
   - Redis 接入，作为偏好热缓存 + LLM 总结缓存

2. **再重构为 Plan-and-Execute（Day 5-6）**
   - 引入 **AgentScope** 框架
   - 把阶段二的 Python 函数拆为 Agent：
     - `IntentionAgent`（Plan 阶段）
     - `OrchestrationAgent`（Execute 阶段）
   - 子 Skill 拆分：`FlightSearchAgent` / `PreferenceMatchAgent` / `DecisionAgent` / `MemoryQueryAgent`
   - 引入 **LazyAgentRegistry**，扫描 `skills/` 目录懒加载

3. **再加两层记忆系统（Day 6）**
   - `ShortTermMemory`（Redis 滑动窗口）
   - `LongTermMemory`（PostgreSQL 持久化）
   - `Summarizer`（异步 LLM 总结，缓存到 Redis）
   - `MemoryManager` 统一入口

4. **再加容错机制（Day 7）**
   - `CircuitBreaker`（LLM 调用 / Selenium 抓取）
   - `retry_with_backoff`（指数退避）
   - 优先级并行调度（`asyncio.gather` 同优先级并行）

5. **最后优化细节、一键部署（Day 8）**
   - 优先级并行调度性能验证
   - SSE 流式输出体验
   - `docker-compose.yml` 一键启动所有服务（前端+后端+PG+Redis）
   - 视觉细节、错误兜底、loading 动画
   - README 和部署文档

**阶段三交付物：**
- 完整的 v2.0 架构（本文档前面章节描述的终态）
- Docker Compose 一键启动
- 可演示、可扩展（新数据源零侵入接入）

---

### 阶段分工速查表

| 能力 | 阶段一 | 阶段二 | 阶段三 |
|------|-------|-------|-------|
| 前端页面 | ✅ 静态 Mock | ✅ 对接真实 API | ✅ 细节打磨 |
| 后端 | ❌ | ✅ FastAPI 裸写 | ✅ + AgentScope |
| 数据源 | ❌ 前端假数据 | ✅ flights_monitor | ✅ 多源注册表 |
| LLM 调用 | ❌ | ✅ 一个函数 | ✅ 多 Agent + 多模型 |
| 记忆系统 | ✅ localStorage | ✅ JSON 文件 | ✅ Redis + PostgreSQL |
| Plan-Execute | ❌ | ❌ 串行 | ✅ 并行调度 |
| Skill Plugin | ❌ | ❌ | ✅ LazyAgentRegistry |
| 容错 | ❌ | ❌ | ✅ 熔断+重试 |
| 部署 | Vercel | Vercel + Railway | Docker Compose |

---

### 阶段一/二和 v2.0 终态架构的关系

**本文档前面（第 0 节~第 13 节）描述的是阶段三完成后的终态架构。**

阶段一、阶段二的实现**刻意简化**，不代表最终形态：
- 阶段二的"普通 Python 函数"会在阶段三被重构为 AgentScope 的 IntentionAgent/OrchestrationAgent
- 阶段二的"JSON 文件记忆"会在阶段三被替换为 Redis+PostgreSQL 两层记忆
- 阶段二的"串行调用"会在阶段三被重构为优先级并行调度

**但核心原则贯穿三个阶段：**
- ✅ Agent 只决策，Tool 只执行（阶段一是前端判断，阶段二/三是后端分层）
- ✅ 数据源抽象（阶段一是 mocks/, 阶段二/三是 data_sources/）
- ✅ 记忆显性化（阶段一 localStorage 展示，阶段二/三 数据库展示）

---

**以下是阶段三完成后的终态架构细节。阶段一只看到「阶段一」章节就够，阶段二只看到「阶段二」章节和本文档的第 4 节（Agent/Tool 契约）就够。**

---

---

## 0. 核心设计原则

### 原则一：Plan-and-Execute 架构

> 采纳自差旅出行助手项目（飞书文档）与 Claude Code coordinator 模式。

**两阶段：**
- **Plan 阶段**：`IntentionAgent` 理解用户意图，输出**调度计划**（agent_schedule），但不执行业务
- **Execute 阶段**：`OrchestrationAgent` 按优先级调度子 Agent，同优先级并行，不同优先级串行

**为什么选 Plan-and-Execute 而不是 ReAct：**
- 多 Agent 协调场景：一次规划好，并行执行，效率高
- 成本可控：只有 IntentionAgent 调 LLM 做规划，其他 Agent 调用链可预测
- 可控性强：调度流程明确，不会陷入死循环

### 原则二：Agent 与 Tool 严格分离（延续 v1）

> **AI 只做决策与语言总结，工具脚本完成所有数据抓取、计算与比较。**

| 层 | 职责 | 是否含 AI |
|---|------|---------|
| **Agent 层** | 意图理解、调度规划、语言生成 | ✅ AI |
| **Tool 层** | 抓数据、算百分比、对比价格 | ❌ 纯代码 |

### 原则三：Skill Plugin 架构 + Progressive Disclosure

> 采纳自飞书文档的 Skill Plugin 设计，每个子 Agent 作为独立 Skill 插件。

- 目录：`skills/{skill-name}/` 下包含 `SKILL.md` + `agent.py`
- `SKILL.md` 是**元数据 + 提示词**（给 IntentionAgent 做调度决策用）
- `agent.py` 是**执行逻辑**（继承 `AgentBase`，暴露 `reply()`）
- `LazyAgentRegistry` 启动时扫描 skills 目录，首次调用时才加载（懒加载）
- **三层 Progressive Disclosure：**
  - 元数据层（所有 Skill 的 name + description）→ 注入 IntentionAgent 的 Prompt
  - 指令层（具体执行说明）→ 单个 Agent 执行时按需加载
  - 资源层（数据文件、代码）→ 实际调用时访问

### 原则四：两层记忆系统（核心差异化）

> **记忆显性化是产品的核心巧思，架构必须把它做扎实。**

**短期记忆 (ShortTermMemory)：**
- 存储：Redis List
- 容量：滑动窗口，最近 10 轮对话
- 生命周期：会话级，TTL 1 小时
- 用途：当前对话连贯性

**长期记忆 (LongTermMemory)：**
- 存储：PostgreSQL 持久化
- 内容：用户偏好、查询历史、点击行为、行程历史
- 生命周期：跨会话，永久
- 用途：个性化判断、记忆显性化展示

**异步 LLM 总结：**
- 对长期聊天历史定期做 200 字摘要
- 缓存到 Redis（TTL 30 分钟）
- 作为 system 消息注入 IntentionAgent

### 原则五：前后端彻底分离（方案 C）

```
Next.js 前端（纯 UI）
     ↕ HTTP/SSE
Python FastAPI + AgentScope 后端（全部业务）
     ↓
PostgreSQL + Redis
```

---

## 1. 技术栈

### 前端
| 层 | 选型 | 理由 |
|---|------|------|
| 框架 | **Next.js 14 (App Router)** | 生态丰富、AI SDK 完善 |
| 语言 | **TypeScript** | 类型安全 |
| 样式 | **Tailwind CSS + shadcn/ui** | 快速构建漂亮界面 |
| 状态 | **React Context + SWR** | 轻量 |
| 通信 | **fetch + SSE（流式返回）** | AI 流式输出体验 |

### 后端
| 层 | 选型 | 理由 |
|---|------|------|
| 框架 | **FastAPI** | Python 异步生态最好 |
| Agent 框架 | **AgentScope** | 飞书文档同款，消息传递 + Actor 模型 |
| ORM | **SQLAlchemy 2.0 (async)** | Python 主流 |
| 数据库 | **PostgreSQL 15** | JSONB + MVCC |
| 缓存 | **Redis 7** | 短期记忆 + 偏好热缓存 + LLM 总结缓存 |
| 数据源 | **flights_monitor (改造版)** | 携程先跑通，其他平台改造后接入 |
| LLM | **可插拔多供应商** | DeepSeek / 通义 / 智谱 / OpenAI 等 |

---

## 2. 项目目录结构

```
meituan/
├── frontend/                           # Next.js 前端（纯 UI）
│   ├── app/
│   │   ├── page.tsx                    # 首页（对话 + GUI 卡片）
│   │   ├── results/page.tsx            # 结果页
│   │   ├── profile/page.tsx            # 个人中心（记忆显性化）
│   │   └── layout.tsx
│   ├── components/
│   │   ├── ChatInput.tsx
│   │   ├── HotDealsCard.tsx
│   │   ├── PersonalizedCard.tsx
│   │   ├── FlightResultCard.tsx
│   │   ├── AIRecommendBadge.tsx
│   │   └── PreferenceItem.tsx
│   ├── lib/
│   │   ├── api-client.ts               # 调后端 FastAPI
│   │   └── sse.ts                      # SSE 流式处理
│   ├── .env.local                      # NEXT_PUBLIC_API_URL
│   └── package.json
│
├── backend/                            # Python 后端（全部业务）
│   ├── main.py                         # FastAPI 入口
│   ├── api/                            # HTTP 路由层
│   │   ├── chat.py                     # POST /api/chat (SSE)
│   │   ├── search.py                   # POST /api/search
│   │   ├── memory.py                   # GET/PATCH /api/memory
│   │   └── recommendations.py          # GET /api/recommendations
│   │
│   ├── agents/                         # 【Plan-and-Execute】核心 Agent
│   │   ├── intention_agent.py          # Plan 阶段（规划者）
│   │   ├── orchestration_agent.py      # Execute 阶段（调度者）
│   │   └── base.py                     # 继承 AgentScope AgentBase
│   │
│   ├── skills/                         # 【Skill Plugin】插件化子 Agent
│   │   ├── intent_parser/              # （由 IntentionAgent 内部使用）
│   │   ├── flight_search/
│   │   │   ├── SKILL.md                # 元数据 + 提示词
│   │   │   └── script/agent.py         # FlightSearchAgent
│   │   ├── preference_match/
│   │   │   ├── SKILL.md
│   │   │   └── script/agent.py         # PreferenceMatchAgent
│   │   ├── decision_maker/
│   │   │   ├── SKILL.md
│   │   │   └── script/agent.py         # DecisionAgent
│   │   ├── memory_query/
│   │   │   ├── SKILL.md
│   │   │   └── script/agent.py
│   │   ├── preference_manager/
│   │   │   ├── SKILL.md
│   │   │   └── script/agent.py         # 追加/覆盖偏好
│   │   └── _registry.py                # LazyAgentRegistry
│   │
│   ├── tools/                          # 【Tool 层】纯代码，无 AI
│   │   ├── fetch_flights.py            # 调 DataSource 抓航班
│   │   ├── compare_prices.py           # 多平台价格对比计算
│   │   ├── analyze_history.py          # 历史均价、低价百分位
│   │   ├── match_preference.py         # 偏好匹配度打分
│   │   └── generate_signals.py         # 生成"值得买"标签
│   │
│   ├── data_sources/                   # 数据源抽象
│   │   ├── base.py                     # DataSource 抽象基类
│   │   ├── ctrip_source.py             # 封装 flights_monitor
│   │   ├── tongcheng_source.py         # 改造后接入
│   │   ├── qunar_source.py             # 改造后接入
│   │   ├── umetrip_source.py           # 航旅纵横，改造后接入
│   │   └── registry.py                 # 数据源注册表
│   │
│   ├── third_party/
│   │   └── flights_monitor/            # git submodule 或 clone 子目录
│   │
│   ├── memory/                         # 【两层记忆系统】
│   │   ├── short_term.py               # Redis 滑窗
│   │   ├── long_term.py                # PostgreSQL 持久化
│   │   ├── summarizer.py               # 异步 LLM 总结
│   │   └── manager.py                  # MemoryManager 统一入口
│   │
│   ├── llm/                            # LLM 抽象层
│   │   ├── client.py                   # 统一调用接口
│   │   ├── config.py                   # 每个 Agent 的模型配置
│   │   └── providers/
│   │       ├── deepseek.py
│   │       ├── qwen.py
│   │       └── zhipu.py
│   │
│   ├── resilience/                     # 容错机制
│   │   ├── circuit_breaker.py          # 熔断器
│   │   └── retry.py                    # 指数退避重试
│   │
│   ├── db/                             # 数据库层
│   │   ├── models.py                   # SQLAlchemy 模型
│   │   ├── session.py                  # async session
│   │   └── migrations/                 # Alembic
│   │
│   ├── config.py                       # 全局配置
│   ├── requirements.txt
│   └── .env                            # DB、Redis、LLM key
│
├── docker-compose.yml                  # PostgreSQL + Redis 一键启动
├── PRD.md
└── ARCHITECTURE.md
```

---

## 3. 架构总图

```
┌─────────────────────────────────────────────────────────────┐
│                    Next.js 前端 (纯 UI)                       │
│    首页(对话+卡片) → 结果页 → 个人中心                         │
└─────────────────────────────────────────────────────────────┘
                          ↕ HTTP / SSE
┌─────────────────────────────────────────────────────────────┐
│                  FastAPI 路由层                                │
│    /chat  /search  /memory  /recommendations                 │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│           【Plan 阶段】IntentionAgent (AgentScope)             │
│   职责: 理解用户自然语言 + 读取短期/长期记忆 + 生成调度计划     │
│   输出: { reasoning, intents, rewritten_query,                │
│           agent_schedule: [{agent, priority, reason}] }       │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│       【Execute 阶段】OrchestrationAgent (AgentScope)         │
│                                                               │
│   - 按 priority 分组                                          │
│   - 同 priority 用 asyncio.gather 并行                        │
│   - 通过 LazyAgentRegistry 取 Skill Agent                     │
│   - 每个 Skill 通过 Msg 通信                                   │
│                                                               │
│   Priority 1 (并行):                                          │
│   ┌─────────────┐ ┌──────────────┐ ┌─────────────┐          │
│   │FlightSearch │ │PreferenceMatch│ │ MemoryQuery │          │
│   └─────────────┘ └──────────────┘ └─────────────┘          │
│         ↓                                                     │
│   Priority 2 (依赖 P1 结果):                                   │
│   ┌─────────────┐                                             │
│   │DecisionMaker│                                             │
│   └─────────────┘                                             │
│                                                               │
│   结果聚合 → 异步触发 MemoryAgent 写回长期记忆                  │
└─────────────────────────────────────────────────────────────┘
                ↓                       ↓
┌──────────────────────┐   ┌────────────────────────────────┐
│   Tool 层 (纯代码)    │   │   Memory 层                     │
│  fetch_flights       │   │   ShortTerm (Redis)             │
│  compare_prices      │   │   LongTerm (PostgreSQL)         │
│  analyze_history     │   │   Summarizer (异步 LLM)          │
│  match_preference    │   └────────────────────────────────┘
│  generate_signals    │
└──────────────────────┘
         ↓
┌──────────────────────────────────────────────────┐
│  DataSource 层                                    │
│  CtripSource (flights_monitor 封装) ✅            │
│  TongchengSource (改造后接入)                      │
│  QunarSource (改造后接入)                          │
│  UmetripSource (改造后接入)                        │
└──────────────────────────────────────────────────┘
```

---

## 4. Agent / Skill / Tool 契约

### IntentionAgent（Plan 阶段）

**继承自 AgentScope `AgentBase`。**

**输入（Msg）：**
```python
content = {
    "user_input": "五一去三亚，600以内",
    "short_term_memory": [...],  # 最近10轮对话
    "long_term_summary": "...",   # LLM 总结的长期偏好
    "available_skills": [         # LazyRegistry 扫描到的 skill 元数据
        {"name": "flight_search", "description": "..."},
        {"name": "preference_match", "description": "..."},
        ...
    ]
}
```

**输出（Msg.content JSON）：**
```json
{
  "reasoning": "用户想在五一期间去三亚旅游，预算600元...",
  "intents": [
    {"type": "flight_search", "confidence": 0.95},
    {"type": "preference_use", "confidence": 0.80}
  ],
  "rewritten_query": "北京→三亚, 2026-05-01至2026-05-03, 预算≤600",
  "key_entities": {
    "origin": "BJS", "destination": "SYX",
    "date_start": "2026-05-01", "date_end": "2026-05-03",
    "budget": 600
  },
  "agent_schedule": [
    {"agent": "flight_search",     "priority": 1, "reason": "用户查询特定航线价格"},
    {"agent": "preference_match",  "priority": 1, "reason": "比较是否符合心理价位"},
    {"agent": "memory_query",      "priority": 1, "reason": "查找是否有类似历史查询"},
    {"agent": "decision_maker",    "priority": 2, "reason": "基于并行结果生成建议"}
  ]
}
```

### OrchestrationAgent（Execute 阶段）

**核心逻辑：**
```python
async def reply(self, intention_msg):
    schedule = json.loads(intention_msg.content)["agent_schedule"]
    context = await self._prepare_context(intention_msg)

    # 按 priority 分组
    groups = defaultdict(list)
    for task in schedule:
        groups[task["priority"]].append(task)

    previous_results = []
    for priority in sorted(groups.keys()):
        tasks = groups[priority]
        # 同优先级并行
        coroutines = [
            self._execute_skill(task, context, previous_results)
            for task in tasks
        ]
        results = await asyncio.gather(*coroutines, return_exceptions=True)
        previous_results.extend(results)

    aggregated = self._aggregate(previous_results)
    asyncio.create_task(self._update_memory_async(aggregated))  # 异步写记忆
    return Msg(name="orchestrator", content=json.dumps(aggregated))
```

### FlightSearchAgent（Skill，AI 只做决策）

**职责：根据意图决定"抓什么数据"，不直接抓。**

**AI 输出（工具调用计划）：**
```json
{
  "tool_calls": [
    {"tool": "fetch_flights",
     "params": {"route": "BJS-SYX", "date": "2026-05-01",
                "platforms": ["ctrip"]}},
    {"tool": "analyze_history",
     "params": {"route": "BJS-SYX", "days": 90}}
  ]
}
```

**后续：Skill agent 拿到 LLM 输出的 tool_calls 后，依次调 `tools/` 下的纯函数。**

### DecisionAgent（Skill，AI 只做语言总结）

**输入：所有 Tool 已经算好的数字结果。**
```json
{
  "flights": [...],
  "price_comparison": {"min": 389, "max": 410, "diff_pct": 5.4},
  "history": {"avg_90d": 540, "percentile": 0.12, "lower_than_avg": 0.43},
  "preference": {"match_score": 0.85, "within_budget": true}
}
```

**AI 输出（一句话建议）：**
```json
{
  "recommendation": "建议现在买。比你的心理价位低35%，且近期持续涨价。",
  "signals": ["近90天最低", "符合心理价位", "节假日稀缺"],
  "confidence": "high"
}
```

**注意：DecisionAgent 不计算任何百分比，它只翻译数字。**

### Tool 层（纯代码示例）

```python
# backend/tools/analyze_history.py
async def analyze_history(route: str, days: int, current_price: int) -> dict:
    """纯代码计算，不涉及 AI"""
    history = await fetch_history_from_cache_or_source(route, days)
    prices = [p.price for p in history]
    avg = sum(prices) / len(prices)
    sorted_prices = sorted(prices)
    percentile = sorted_prices.index(current_price) / len(sorted_prices) \
                 if current_price in sorted_prices else 0
    return {
        "avg_90d": round(avg),
        "percentile": percentile,
        "lower_than_avg": round((avg - current_price) / avg, 2)
    }
```

---

## 5. DataSource 层（对接 flights_monitor）

### 抽象基类

```python
# backend/data_sources/base.py
from abc import ABC, abstractmethod

class DataSource(ABC):
    name: str

    @abstractmethod
    async def search_flights(self, origin: str, destination: str,
                             date_start: str, date_end: str) -> list[dict]:
        pass

    @abstractmethod
    async def get_history_prices(self, route: str, days: int) -> list[dict]:
        pass
```

### 携程数据源（基于 flights_monitor）

```python
# backend/data_sources/ctrip_source.py
from third_party.flights_monitor import discover_api, ctrip_api
from .base import DataSource

class CtripSource(DataSource):
    name = "ctrip"

    async def search_flights(self, origin, destination, date_start, date_end):
        # 调用 flights_monitor 的 FuzzySearch 或逐城搜索
        raw_results = await self._run_fuzzysearch_in_thread(
            dep_city_code=origin,
            date_range=(date_start, date_end)
        )
        # 转换为标准格式
        return [self._normalize(r) for r in raw_results]

    async def _run_fuzzysearch_in_thread(self, **kwargs):
        """Selenium 是同步阻塞的，用 asyncio 线程池包装"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, discover_api.search, **kwargs)
```

### 数据源注册表

```python
# backend/data_sources/registry.py
_sources = {}

def register(source: DataSource):
    _sources[source.name] = source

def get(name: str) -> DataSource:
    return _sources[name]

def get_active() -> list[DataSource]:
    return [s for s in _sources.values() if s.enabled]
```

**未来扩展：** 你改造 flights_monitor 支持其他平台后，在 `data_sources/` 下新建 `tongcheng_source.py`、`qunar_source.py`，实现同样接口，注册到 registry 即可，上层 Agent / Tool 零修改。

**Selenium 的坑：** flights_monitor 基于 Selenium 需要 Chrome，每次请求开浏览器很慢。**建议策略：**
- 热门航线结果缓存到 Redis，TTL 30 分钟
- 冷启动时批量抓取预热
- 后期考虑改造 flights_monitor 为无头 HTTP 抓取（不用 Selenium）

---

## 6. 两层记忆系统实现

### 短期记忆（Redis）

```python
# backend/memory/short_term.py
class ShortTermMemory:
    def __init__(self, redis_client, max_turns=10, ttl=3600):
        self.redis = redis_client
        self.max_turns = max_turns
        self.ttl = ttl

    async def add_message(self, user_id: str, role: str, content: str):
        key = f"memory:short:{user_id}"
        await self.redis.rpush(key, json.dumps({"role": role, "content": content}))
        await self.redis.ltrim(key, -self.max_turns, -1)  # 保留最近 N 条
        await self.redis.expire(key, self.ttl)

    async def get_recent(self, user_id: str, n: int = 10) -> list:
        key = f"memory:short:{user_id}"
        items = await self.redis.lrange(key, -n, -1)
        return [json.loads(i) for i in items]
```

### 长期记忆（PostgreSQL）

**表结构：**
```sql
-- 用户偏好（核心）
CREATE TABLE preferences (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(64) NOT NULL,
    field VARCHAR(64) NOT NULL,      -- 'frequent_dest', 'price_anchor', etc.
    value JSONB NOT NULL,
    source VARCHAR(16),               -- 'auto' | 'manual'
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, field)
);

-- 查询历史
CREATE TABLE query_history (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(64),
    intent JSONB,
    rewritten_query TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 点击行为
CREATE TABLE click_history (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(64),
    flight_info JSONB,
    price INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 聊天历史全量（用于异步总结）
CREATE TABLE chat_history (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(64),
    role VARCHAR(16),
    content TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### 异步 LLM 总结

```python
# backend/memory/summarizer.py
async def summarize_long_term(user_id: str) -> str:
    # 1. 先查 Redis 缓存
    cache_key = f"memory:summary:{user_id}"
    cached = await redis.get(cache_key)
    if cached:
        return cached.decode()

    # 2. 从 PostgreSQL 查历史
    history = await db.fetch_chat_history(user_id, limit=50)

    # 3. 调 LLM 生成 200 字摘要
    summary = await llm.call(
        agent="summarizer",
        messages=[{"role": "user", "content": build_summary_prompt(history)}]
    )

    # 4. 写回 Redis（TTL 30 分钟）
    await redis.setex(cache_key, 1800, summary)
    return summary
```

### MemoryManager 统一入口

```python
# backend/memory/manager.py
class MemoryManager:
    async def get_context_for_agent(self, user_id: str, query: str) -> dict:
        short_term = await self.short.get_recent(user_id)
        long_term_summary = await self.summarizer.summarize_long_term(user_id)
        preferences = await self.long.get_all_preferences(user_id)
        return {
            "short_term": short_term,
            "long_term_summary": long_term_summary,
            "preferences": preferences
        }

    async def add_message(self, user_id: str, role: str, content: str):
        # Write-Through: 同时写 Redis 和 PostgreSQL
        await asyncio.gather(
            self.short.add_message(user_id, role, content),
            self.long.add_message(user_id, role, content)
        )
```

---

## 7. LazyAgentRegistry（Skill 插件懒加载）

```python
# backend/skills/_registry.py
import importlib.util
from pathlib import Path

class LazyAgentRegistry:
    def __init__(self, skills_dir: Path):
        self.skills_dir = skills_dir
        self.skill_paths = {}   # name → script path
        self.metadata = {}      # name → SKILL.md metadata
        self.cache = {}         # name → instance
        self._discover()

    def _discover(self):
        """启动时扫描，只记录位置，不加载"""
        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir(): continue
            script = skill_dir / "script" / "agent.py"
            md = skill_dir / "SKILL.md"
            if script.exists() and md.exists():
                name = skill_dir.name
                self.skill_paths[name] = script
                self.metadata[name] = self._parse_skill_md(md)

    def __getitem__(self, name: str):
        """首次访问时懒加载"""
        if name in self.cache:
            return self.cache[name]
        script_path = self.skill_paths[name]
        spec = importlib.util.spec_from_file_location(name, script_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        # 反射查找继承 AgentBase 的类
        agent_cls = self._find_agent_class(module)
        instance = agent_cls(memory_manager=self.memory_manager)
        self.cache[name] = instance
        return instance

    def list_metadata(self) -> list[dict]:
        """供 IntentionAgent 做调度决策"""
        return [{"name": n, **m} for n, m in self.metadata.items()]
```

---

## 8. 熔断器 + 重试

```python
# backend/resilience/circuit_breaker.py
class CircuitBreaker:
    def __init__(self, fail_threshold=5, recovery_timeout=60):
        self.state = "closed"  # closed | open | half_open
        self.fail_count = 0
        self.last_fail_time = None
        self.fail_threshold = fail_threshold
        self.recovery_timeout = recovery_timeout

    def raise_if_open(self):
        if self.state == "open":
            if time.time() - self.last_fail_time > self.recovery_timeout:
                self.state = "half_open"
            else:
                raise CircuitOpenError()
    # ... record_success / record_failure
```

```python
# backend/resilience/retry.py
async def retry_with_backoff(fn, max_retries=3, base=1.0, max_delay=30.0):
    delay = base
    for i in range(max_retries):
        try:
            return await fn()
        except Exception as e:
            if not is_retryable(e): raise
            if i == max_retries - 1: raise
            await asyncio.sleep(min(delay, max_delay))
            delay *= 2
```

**使用场景：** LLM 调用、Selenium 抓数据、Redis/PG 异常。

---

## 9. 完整请求流转示例

**用户输入：** "五一去三亚，600以内"

```
[1] 前端 → POST /api/search { user_id: "u1", message: "..." }

[2] FastAPI 路由：
    ├─ memory_manager.get_context_for_agent(u1, message)
    │    ↓ short_term (Redis) + long_term_summary (LLM 摘要) + preferences (PG)
    │
    ├─ 构造 Msg，送入 IntentionAgent
    │    ↓ AgentScope Actor 模型消息传递
    │
    ├─ IntentionAgent.reply() → 返回 agent_schedule JSON
    │    ↓
    ├─ OrchestrationAgent.reply(schedule)
    │    ├─ _prepare_context
    │    ├─ Priority 1 并行执行（asyncio.gather）:
    │    │    ├─ FlightSearchAgent
    │    │    │    ↓ AI 生成 tool_calls
    │    │    │    ↓ 调 tools/fetch_flights → CtripSource → flights_monitor
    │    │    │    ↓ 调 tools/compare_prices → 纯代码算 min/max
    │    │    │    ↓ 调 tools/analyze_history → 纯代码算均价/百分位
    │    │    │
    │    │    ├─ PreferenceMatchAgent
    │    │    │    ↓ 读长期记忆偏好
    │    │    │    ↓ 调 tools/match_preference 算匹配度
    │    │    │
    │    │    └─ MemoryQueryAgent
    │    │         ↓ 查历史查询
    │    │
    │    ├─ Priority 2 (依赖 P1 结果):
    │    │    └─ DecisionAgent
    │    │         ↓ 接收所有 P1 结构化数字
    │    │         ↓ AI 生成一句话建议 + 信号标签
    │    │
    │    └─ _aggregate_results → 异步触发 _update_memory
    │
    └─ 返回前端: { flights, signals, recommendation }

[3] 前端渲染结果卡片 + 更新个人中心（偏好变化标记）
```

---

## 10. 执行步骤（三阶段细化）

### 阶段一：MVP 前端页面部署（Day 1，4-6 小时）

| # | 任务 | 输出 | 关键点 |
|---|------|------|--------|
| 1.1 | `pnpm create next-app frontend --ts --tailwind --app` | 项目骨架 | - |
| 1.2 | 安装 shadcn/ui，初始化组件库 | UI 基础 | - |
| 1.3 | 写 `frontend/mocks/` 假数据（flights.json / preferences.json / hot-deals.json） | 假数据就位 | 5 条真实感航线 |
| 1.4 | 首页：对话输入框 + 热门低价卡 + 个性化卡片 | app/page.tsx | 先做布局 |
| 1.5 | 结果页：结果卡片 + AI 建议 + 信号标签 | app/results/page.tsx | - |
| 1.6 | 个人中心：偏好列表 + 编辑/删除（localStorage） | app/profile/page.tsx | - |
| 1.7 | 简单关键词路由：对话输入 → 跳转结果页 | 交互闭环 | 不调 LLM |
| 1.8 | `vercel --prod` 一键部署 | 线上 URL | - |

**阶段一验收：**
- [ ] 打开 URL 看到首页
- [ ] 点击卡片跳转结果页
- [ ] 结果页能看到 AI 建议（写死的）
- [ ] 个人中心能编辑偏好，刷新不丢

---

### 阶段二：真实数据上线并部署（Day 2-3，6-10 小时）

**Day 2：后端裸搭 + 数据源接入（4-6 小时）**

| # | 任务 | 输出 |
|---|------|------|
| 2.1 | `backend/` 初始化：`uv init` + FastAPI + httpx + python-dotenv | requirements.txt |
| 2.2 | clone flights_monitor 到 `backend/third_party/flights_monitor/` | Selenium 可跑 |
| 2.3 | 写 `backend/data_sources/ctrip_source.py` 封装 flights_monitor | 返回标准化航班数据 |
| 2.4 | 写 `backend/llm.py`：`parse_intent()` + `generate_recommendation()` | 接 DeepSeek |
| 2.5 | 写 `backend/memory.py`：读写 `memory.json` 文件 | 偏好可持久化 |
| 2.6 | 写 `backend/main.py`：FastAPI 3 个路由（/search, /memory, /recommendations） | 后端跑通 |
| 2.7 | 本地 curl 测试全流程 | ✅ |

**Day 3：前后端对接 + 部署（4 小时）**

| # | 任务 | 输出 |
|---|------|------|
| 3.1 | 前端 `lib/api-client.ts` 替换 mocks 调用真实 API | 前后端通 |
| 3.2 | 部署前端到 Vercel | 前端在线 |
| 3.3 | 部署后端到 Railway（支持 Chrome + Python） | 后端在线 |
| 3.4 | 环境变量串起来（API_URL、LLM_KEY、DB 暂无） | 线上跑通 |
| 3.5 | 热门航线预热脚本（启动时批量跑 flights_monitor） | 首屏快 |

**阶段二验收：**
- [ ] 输入"五一去三亚"能返回真实携程数据
- [ ] AI 建议是 LLM 真实生成的
- [ ] 编辑偏好后下次搜索能看到变化
- [ ] 线上 URL 可分享

**阶段二明确不做：**
- ❌ AgentScope（Python 函数串行即可）
- ❌ PostgreSQL / Redis（JSON 文件）
- ❌ 多 Agent / 并行调度
- ❌ 熔断器 / 异步总结

---

### 阶段三：架构精细化 + 一键部署（Day 4-8，4-6 天）

**Day 4：数据库接入（先做这个）**

| # | 任务 | 输出 |
|---|------|------|
| 4.1 | `docker-compose.yml` 启 PostgreSQL + Redis | 本地双服务 |
| 4.2 | SQLAlchemy 2.0 async + asyncpg + Alembic 初始化 | ORM 就绪 |
| 4.3 | 建表：preferences / query_history / click_history / chat_history | schema 就绪 |
| 4.4 | 从 JSON 文件迁移到 PostgreSQL | 数据搬家 |
| 4.5 | Redis 接入（偏好热缓存） | 性能提升 |

**Day 5-6：重构为 Plan-and-Execute（引入 AgentScope）**

| # | 任务 | 输出 |
|---|------|------|
| 5.1 | 安装 AgentScope，熟悉 AgentBase + Msg + 异步 reply | 框架就绪 |
| 5.2 | 把阶段二的 `parse_intent()` 重构为 `IntentionAgent`（Plan 阶段） | Plan 输出正确 schedule |
| 5.3 | 写 `OrchestrationAgent`（Execute 阶段，优先级并行） | Execute 可运行 |
| 5.4 | 拆 Skill：FlightSearchAgent / PreferenceMatchAgent / DecisionAgent / MemoryQueryAgent | skills/ 完整 |
| 5.5 | 每个 Skill 写 `SKILL.md` 元数据 | Progressive Disclosure |
| 5.6 | 写 `LazyAgentRegistry`，扫描 skills/ 目录懒加载 | 插件化 |
| 5.7 | 5 个 Tool 纯函数（fetch_flights / compare_prices / analyze_history / match_preference / generate_signals） | tools/ 完整 |

**Day 6-7：两层记忆 + 容错**

| # | 任务 | 输出 |
|---|------|------|
| 6.1 | ShortTermMemory（Redis 滑动窗口） | 短期记忆 |
| 6.2 | LongTermMemory（PostgreSQL 持久化） | 长期记忆 |
| 6.3 | 异步 LLM 总结 + Redis 缓存 | 摘要机制 |
| 6.4 | MemoryManager 统一入口 | 对外一个接口 |
| 6.5 | CircuitBreaker（LLM 调用 + Selenium） | 容错 |
| 6.6 | retry_with_backoff（指数退避） | 重试 |
| 6.7 | 优先级并行调度（asyncio.gather） | 性能 |

**Day 8：细节优化 + 一键部署**

| # | 任务 | 输出 |
|---|------|------|
| 8.1 | SSE 流式返回（AI 建议逐字输出） | 体验感 |
| 8.2 | 视觉细节、loading、错误兜底 | 可演示 |
| 8.3 | `docker-compose.yml` 整合前端+后端+PG+Redis | 一键启动 |
| 8.4 | README + 部署文档 | 可交付 |

**阶段三验收：**
- [ ] 完整 Plan-and-Execute 架构跑通
- [ ] 同优先级 Agent 并行执行（响应时间可度量）
- [ ] 两层记忆可视化（个人中心能看到短期和长期）
- [ ] `docker compose up` 一键启动所有服务
- [ ] 新增数据源零侵入接入（接口稳定）

---

## 11. 关键决策记录

| 决策 | v1 | v2 | 理由 |
|------|----|----|------|
| 后端语言 | TypeScript | **Python** | AgentScope + flights_monitor 都是 Python 原生 |
| 前后端架构 | Next.js 全栈 | **彻底分离** | 后端切 Python 后不得不分 |
| Agent 框架 | 自建 | **AgentScope** | 消息传递、Actor、插件化支持完善 |
| 架构模式 | 串行 Pipeline | **Plan-and-Execute** | 多 Agent 协调更高效，可并行 |
| 调度 | 串行 | **优先级并行** | 同优先级 asyncio.gather |
| 记忆 | SQLite | **PG + Redis 两层** | 专业方案，支持异步总结 |
| Skill 机制 | 函数调用 | **Plugin + Lazy Registry** | 插件化、零配置 |
| 数据源 | Mock JSON | **flights_monitor 真实数据** | 携程先跑通，其他改造后接入 |

---

## 12. 待决策 / 待改造

- [ ] flights_monitor 的改造进度：同程/去哪儿/航旅纵横 何时能接入
- [ ] LLM 模型选型：每个 Agent 对应哪家模型（建议做 A/B 对比）
- [ ] Selenium 性能瓶颈：是否要改造 flights_monitor 为纯 HTTP 抓取
- [ ] PostgreSQL / Redis 部署：本地 docker-compose 还是云服务

---

## 13. 风险与应对

| 风险 | 影响 | 应对 |
|------|------|------|
| Selenium 抓取慢（>5s） | 用户体验差 | 热门航线预热 + Redis 缓存 30 分钟 |
| 携程反爬 | 数据源不可用 | retry_with_backoff + CircuitBreaker 降级 |
| AgentScope 学习成本 | 开发慢 | 先用最小子集（AgentBase + Msg + 异步 reply） |
| LLM 输出 JSON 不稳定 | Plan 失败 | 严格 Prompt + 解析失败兜底 + 重试 |
| 改造 flights_monitor 延期 | 数据源不足 | 其他平台先返回空，前端做提示 |

---

**下一步：确认架构无误后，从 Day 1 的 docker-compose 开始执行。**
