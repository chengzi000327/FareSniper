# FareSniper 后端重构方案 0414

## 1. 范围

- 进行后端整体重构，但保持现有业务流程不变。
- 用 Graph-native 架构替换当前 agent 编排运行时。
- 保留 skill 概念，但重构为渐进式加载与结构化执行。
- 将编排、context engineering、内部函数调用、可观测性、模块契约一起重构，不做局部补丁式改造。

## 2. 核心方向

- 编排框架：`LangGraph`
- LLM 集成层：`LangChain`
- Workflow Trace 与图调试：`LangSmith`
- Prompt 输入输出监控：`Langfuse`
- 契约约束：`Pydantic` 结构化 Schema
- API 层：`FastAPI`

目标不是“在旧后端外面套一层 LangChain”，而是让 graph runtime 成为后端唯一的编排权威。

## 3. 后端分层与运行时

后端需要从现在这种 `API -> services -> agents -> tools` 的混合调用模式，切换为 graph 驱动的运行时。`FastAPI` 只负责协议边界和入站出站，`LangGraph` 负责唯一的流程编排，`LangChain` 只负责模型调用、prompt 模板、structured output 和 tool binding。

### 3.1 目标分层

- `api/`
  - HTTP / SSE 接口
  - 请求校验
  - 鉴权与 session 识别
  - graph 调用入口
- `application/graph/`
  - `LangGraph` state 定义
  - node 实现
  - router 与 edges
  - graph factory
- `application/contracts/`
  - 全局共享 `Pydantic` 契约
  - `WorkflowState`
  - 节点输入输出 Schema
  - structured output Schema
- `application/context/`
  - session bootstrap
  - system / developer / user message 装配
  - memory 注入
  - permission 与 runtime policy 注入
  - context budget 管理
- `application/skills/`
  - skill metadata registry
  - 渐进式加载
  - skill prompt 片段
  - skill adapter 与能力描述
- `domain/`
  - 稳定业务概念
  - 搜索意图
  - 用户偏好
  - 价格信号
  - 决策结论
- `infrastructure/llm/`
  - 模型客户端
  - LangChain 封装
  - structured output 调用辅助层
  - provider 配置
- `infrastructure/observability/`
  - LangSmith tracing
  - Langfuse prompt logging
  - metrics 与 correlation id
- `infrastructure/repositories/`
  - PostgreSQL / Redis 访问
  - memory repository
  - prompt / skill registry
- `tools/`
  - 纯计算或受控外部调用
  - 航班抓取
  - 价格比较
  - 偏好评分
  - 信号生成

### 3.2 运行时规则

运行时主链路应变为：

`FastAPI endpoint -> session bootstrap -> graph invocation -> node-by-node execution -> structured final response -> async memory writeback`

硬性约束：

- 编排只能存在一处：`LangGraph`
- 节点之间只能传结构化 state
- 内部函数调用要么是 graph node，要么是 node 内受控步骤
- 自由文本不能成为模块间隐式契约
- 旧的 `intention_agent.py` 与 `orchestration_agent.py` 不再是长期核心抽象

### 3.3 顶层 WorkflowState

graph 运行时至少需要维护这些统一字段：

- `request_context`
- `session_context`
- `message_stack`
- `memory_context`
- `skill_context`
- `workflow_plan`
- `tool_results`
- `decision_context`
- `final_response`
- `execution_trace`
- `errors`

## 4. Graph 设计与数据流

新 graph 需要保持当前业务主流程不变：

`意图理解 -> 并行查价 / 记忆 / 偏好分析 -> 决策 -> 记忆更新 -> 响应输出`

但每个阶段都必须变成显式 graph node，并带有可验证的 typed contract 和可追踪的 state transition。

### 4.1 推荐 Graph 节点

#### 节点 A：`bootstrap_session_context`

职责：

- 创建 correlation id 和 session id
- 加载运行时配置
- 组装 system / developer / user 上下文包
- 挂载 permissions、memory summary、skill summaries、recent messages

输入：

- raw request
- user id
- session id

输出：

- `session_context`
- `message_stack`
- `context_budget`

#### 节点 B：`parse_user_intent`

职责：

- 把用户自然语言解析为标准化搜索意图
- 提取约束、预算、日期范围、航线偏好、歧义标记
- 生成机器可读 query intent，而不是只生成一段解释文本

输出：

- `normalized_intent`
- `intent_confidence`
- `missing_slots`
- `execution_candidates`

#### 节点 C：`hydrate_memory_context`

职责：

- 获取用户偏好画像
- 获取短期对话上下文
- 获取长期记忆摘要
- 获取最近查询与点击历史

输出：

- `memory_context`

#### 节点 D：`select_skills`

职责：

- 判断当前 workflow 需要哪些 skills
- 第一阶段只加载 metadata
- 决定是否需要进一步加载详细 prompt / resources

输出：

- `skill_context.selected_skills`
- `skill_context.load_plan`

#### 节点 E：`build_execution_plan`

职责：

- 结合 `normalized_intent`、`memory_context`、`selected_skills`
- 决定下游模块哪些必须执行
- 定义并行分支、结构化输出要求、fallback 分支

输出：

- `workflow_plan`
  - 待执行节点
  - 并行分组
  - 必须满足的 response schemas
  - fallback branches

#### 节点 F1：`run_flight_search`

职责：

- 调用航班数据源
- 归一化上游 payload
- 产出规范化 `FlightCandidate` 集合

#### 节点 F2：`run_preference_match`

职责：

- 按显式偏好与隐式偏好对候选结果打分
- 用结构化字段解释命中与冲突原因

#### 节点 F3：`run_memory_reasoning`

职责：

- 从用户记忆中提取当前查询相关的锚点
- 判断哪些被记住的事实会实质影响推荐结果

当计划要求三者都执行时，这三个节点应并行运行。

#### 节点 G：`synthesize_decision`

职责：

- 合并搜索结果、偏好匹配结果、记忆推理结果、价格信号
- 输出结构化决策结论
- 生成面向前端的推荐产物

输出：

- `decision_context`
- `final_response.recommendation`

#### 节点 H：`render_response`

职责：

- 生成最终 API 响应或流式输出分片
- 保留前端消费所需的结构化字段

输出：

- `final_response`

#### 节点 I：`schedule_memory_writeback`

职责：

- 异步写入 query history
- 更新 memory candidates
- 必要时刷新 summary cache

输出：

- `memory_writeback_receipt`

### 4.2 串行与并行边界

串行阶段：

- `bootstrap_session_context`
- `parse_user_intent`
- `hydrate_memory_context`
- `select_skills`
- `build_execution_plan`
- `synthesize_decision`
- `render_response`

并行阶段：

- `run_flight_search`
- `run_preference_match`
- `run_memory_reasoning`

响应后异步阶段：

- `schedule_memory_writeback`

原因：

- session bootstrap 必须最先执行，因为下游节点都依赖统一 message envelope 与 runtime policy
- 意图解析必须先于 planning，因为后续模块依赖标准化 intent
- skill selection 必须先于执行计划，因为 graph 需要先知道可加载能力与 context budget 消耗
- 查价、偏好匹配、记忆推理在 intent 和 context 固定后彼此独立，适合并行
- 决策综合必须串行，因为它依赖所有并行分支产物

### 4.3 节点所有权模型

每个节点只能拥有一个主要职责和一个主要输出 Schema。

例如：

- `parse_user_intent` 拥有 `NormalizedIntent`
- `run_flight_search` 拥有 `FlightSearchResult`
- `run_preference_match` 拥有 `PreferenceMatchResult`
- `run_memory_reasoning` 拥有 `MemoryReasoningResult`
- `synthesize_decision` 拥有 `DecisionResult`

任何节点都不能输出“半结构化 blob”让下游节点自行猜测含义。如果两个模块共享同一个业务概念，该概念必须提升为共享 contract。

### 4.4 Adapter Layer 要求

由于不同模块会消费不同输入、产出不同输出，graph 内必须显式定义 adapter 边界。

必须存在的 adapter 类型：

- request adapters
  - 把 HTTP request payload 转为 `WorkflowRequest`
- context adapters
  - 把 memory repository 对象转为 prompt-safe 摘要和结构化 facts
- tool adapters
  - 把内部函数结果与外部数据源 payload 转为 canonical result schemas
- response adapters
  - 把 graph 输出转为前端 DTO 与 SSE 事件

这个 adapter layer 是让 `response_format` 真正可执行的关键。否则每个节点都会把存储形状、工具形状或前端形状泄漏进 graph，最终破坏结构化契约。

## 5. 结构化输出与 Response Format 契约

当前后端文档并没有把 structured output 视为一等架构规则。重构后，这必须成为硬约束。

目标不是“让模型顺便返回 JSON”，而是：

- 每个 graph node 都消费 typed input
- 每个 graph node 都输出 typed output
- 每次 LLM 调用都被显式 output schema 约束
- 下游节点只能依赖声明过的字段，不能依赖 prompt 文案措辞
- 中间推理过程要通过显式 reasoning artifacts 暴露，而不是通过黑盒 chain-of-thought 文本传递

### 5.1 契约规则

硬性规则：

- 每个 node 必须定义 input schema 和 output schema
- 每个 LLM 节点必须声明 `response_format` 或等价 schema binding
- 下游节点不能从上游 prose 文本里再解析出本应结构化存在的字段
- adapter 可以转换 shape，但不能凭空发明未声明语义
- 所有共享 schema 必须收口到 `application/contracts/`

建议目录：

- `application/contracts/workflow.py`
- `application/contracts/session.py`
- `application/contracts/intent.py`
- `application/contracts/memory.py`
- `application/contracts/skills.py`
- `application/contracts/search.py`
- `application/contracts/preference.py`
- `application/contracts/decision.py`
- `application/contracts/response.py`

### 5.2 核心共享 Schema

graph 至少需要统一这些模型：

- `WorkflowRequest`
- `SessionContext`
- `ContextEnvelope`
- `NormalizedIntent`
- `MemoryContext`
- `SkillSelection`
- `ExecutionPlan`
- `FlightCandidate`
- `FlightSearchResult`
- `PreferenceConstraint`
- `PreferenceMatchResult`
- `MemoryReasoningResult`
- `DecisionSignal`
- `DecisionResult`
- `FrontendResponse`
- `WorkflowError`

这些模型才是稳定契约。数据库实体、外部 API payload、prompt 文本都不能成为事实标准。

### 5.3 契约示例

`parse_user_intent` 不能只输出一段自由文本：

`"用户想在五一去三亚，预算 600 内，且不想坐红眼航班。"`

它应输出这样的结构化对象：

```json
{
  "normalized_intent": {
    "origin": { "city": "北京", "iata_code": "BJS", "confidence": 0.81 },
    "destination": { "city": "三亚", "iata_code": "SYX", "confidence": 0.98 },
    "date_window": {
      "start_date": "2026-04-30",
      "end_date": "2026-05-03",
      "is_flexible": false
    },
    "budget_cny": 600,
    "constraints": [
      { "type": "avoid_red_eye", "value": true }
    ],
    "ambiguities": [],
    "intent_confidence": "high"
  }
}
```

这个结构化对象才是下游模块的真实输入。

### 5.4 各节点 Response Format 绑定

每个 LLM 节点都要定义 schema 绑定策略：

- `parse_user_intent`
  - 输出：`NormalizedIntent`
- `select_skills`
  - 输出：`SkillSelection`
- `build_execution_plan`
  - 输出：`ExecutionPlan`
- `run_memory_reasoning`
  - 输出：`MemoryReasoningResult`
- `synthesize_decision`
  - 输出：`DecisionResult`
- `render_response`
  - 输出：`FrontendResponse`

每个 schema 都应包含：

- 必要业务字段
- confidence 字段
- ambiguity / insufficiency 标记
- 用于分支路由的 enum 字段
- 可追踪 reasoning artifact，但不暴露原始 chain-of-thought

### 5.5 用结构化 Reasoning Artifacts 替代原始 CoT

你希望通过结构化输出支撑类似 CoT 的能力。正确做法不是保留无限制 chain-of-thought，而是定义受边界约束的 reasoning artifacts，让 graph 和调试平台都能消费。

建议每个关键节点输出这类字段：

- `decision_factors`
- `evidence_refs`
- `applied_preferences`
- `rejected_candidates`
- `branch_reason`
- `missing_information`
- `confidence_explanation`

例如：

```json
{
  "decision_factors": [
    {
      "factor_type": "price_vs_anchor",
      "summary": "当前价格比用户心理价位低 35%",
      "weight": 0.92
    },
    {
      "factor_type": "holiday_scarcity",
      "summary": "五一库存历史上稀缺",
      "weight": 0.73
    }
  ],
  "rejected_candidates": [
    {
      "candidate_id": "MU-2026-04-30-001",
      "reason_code": "violates_departure_time_preference"
    }
  ],
  "branch_reason": "buy_now",
  "confidence_explanation": "高置信度，因为价格、时间与记忆锚点同时对齐"
}
```

这类结构化工件既能支撑 explainability，也能支撑下游节点、trace 系统和前端展示。

### 5.6 模块间 Adapter 策略

graph 中的不同模块会拥有不同内部表示。为了避免 contract drift，必须显式定义 adapter。

必须存在的 adapter：

- `IntentToSearchAdapter`
  - 把 `NormalizedIntent` 转为数据源查询参数
- `SearchToPreferenceAdapter`
  - 把 `FlightCandidate` 集合转为偏好评分输入
- `MemoryToPromptAdapter`
  - 把 memory rows 转为 prompt-safe facts 和摘要
- `DecisionToFrontendAdapter`
  - 把 `DecisionResult` 转为前端卡片、徽标、理由、CTA
- `SkillSelectionToContextAdapter`
  - 把 skill registry metadata 转为真正注入 prompt 的 context blocks

没有这层 adapter，节点就会直接依赖 repository shape 或外部 payload shape，graph 的可替换性会迅速崩坏。

### 5.7 校验与失败语义

structured output 只有在“校验失败也是一等运行时事件”的前提下才有意义。

必须支持：

- schema 校验失败转为 typed graph error
- 每个节点显式声明是否允许 validation retry
- retry policy 属于 node metadata
- malformed output 必须同时记录到 LangSmith 和 Langfuse，并带 correlation id
- 除非 graph 明确声明 fallback branch，否则下游节点不能消费无效 payload

典型失败场景：

- `NormalizedIntent` 缺少 destination code
- `ExecutionPlan` 中出现非法 enum
- `DecisionResult` 引用了不存在于 search results 中的 candidate id

### 5.8 版本管理

这些 contracts 后续一定会演进，所以重要 schema 必须带版本信息。

建议字段：

- `schema_name`
- `schema_version`
- `generated_by`
- `generated_at`

尤其适用于：

- `ExecutionPlan`
- `DecisionResult`
- `FrontendResponse`

这样可以减少 prompt、adapter 或前端协议变化时的静默破坏。

## 6. Session 注入、Context Engineering 与 Skill 渐进加载

这部分是本次后端重构的核心，因为你明确要求在用户 session 真正进入执行图之前，必须先把 system prompt、developer 约束、permissions、用户记忆、skills 摘要等内容装配好，再进入会话执行。

因此，session 不是“收到用户消息后顺手拼一下上下文”，而是一条独立的 bootstrap pipeline。

### 6.1 核心原则

- 先构造 session context，再进入业务 graph
- context 注入必须有固定顺序，不能每个节点各自拼 prompt
- skill 不应一次性全部注入，而应按 metadata -> instruction -> resource 逐步披露
- memory 注入必须区分“可推理事实”和“可展示文案”
- permission 与 developer policy 必须显式进入 context envelope，而不是散落在代码里
- context budget 必须是运行时的一等资源，不能无限堆叠

### 6.2 推荐的 Session Bootstrap 顺序

在进入核心 graph 前，统一构造 `ContextEnvelope`：

1. `system_base`
2. `developer_policy`
3. `runtime_permissions`
4. `user_profile_memory`
5. `user_long_term_summary`
6. `recent_session_history`
7. `skill_metadata_summaries`
8. `current_user_message`

具体说明：

#### 1. `system_base`

放最稳定、最上层的系统角色定义：

- 这是一个特价机票发现与判断系统
- 输出必须遵循结构化约束
- 不允许跳过 schema
- 不允许虚构数据源结果

#### 2. `developer_policy`

放运行时级别的开发者约束：

- 哪些字段必须返回
- 哪些模块可以调用哪些 tools
- 哪些失败必须回退
- 哪些信息不能暴露给用户

这部分相当于统一的“后端行为护栏”。

#### 3. `runtime_permissions`

放权限与环境信息：

- 当前用户可访问的数据范围
- 哪些技能或内部函数可调用
- 是否允许外部搜索 / 第三方数据源
- 当前 session 的安全边界

这样 permission 就变成显式上下文，不再是隐藏条件。

#### 4. `user_profile_memory`

注入显式用户画像：

- 常去城市
- 心理价位
- 航司偏好
- 时间偏好
- 近期关注目的地

这里使用结构化 memory facts，而不是自然语言散文。

#### 5. `user_long_term_summary`

注入长期摘要：

- 用户长期查询行为摘要
- 用户长期偏好趋势
- 风险提示或例外习惯

这部分是摘要层，不替代结构化 facts。

#### 6. `recent_session_history`

注入短期上下文：

- 最近几轮用户消息
- 最近几轮系统关键响应摘要
- 当前 session 未完成槽位

#### 7. `skill_metadata_summaries`

这里只注入 skill 的 metadata：

- 名称
- 作用
- 触发条件
- 需要的输入
- 可能产出的结构化输出类型

不能在这一层把所有 skill 详细指令全部塞入上下文。

#### 8. `current_user_message`

最后再放当前用户本次输入，避免它被早期噪音淹没。

### 6.3 为什么必须固定顺序

如果没有统一顺序，就会出现这些问题：

- memory 和 skill 提示互相覆盖，模型不知道谁优先
- developer policy 在某些节点缺失，导致行为漂移
- permissions 有时在 prompt 里，有时在代码判断里，无法 trace
- 当前用户输入被过早扩展，导致核心槽位提取偏移

固定顺序的目的不是形式美观，而是为了让 session 装配变成可测试、可追踪、可重现的运行时步骤。

### 6.4 Progressive Skill Loading 模型

skill 要继续保留，但必须变成渐进式加载，而不是一次性把全部 `SKILL.md` 内容塞进上下文。

建议分三层：

#### 第一层：Metadata Layer

默认始终可见，内容包括：

- `skill_name`
- `description`
- `trigger_conditions`
- `input_schema_refs`
- `output_schema_refs`
- `cost_hint`

用途：

- 给 `select_skills` 节点做选择
- 给 `build_execution_plan` 节点判断是否需要加载 skill

#### 第二层：Instruction Layer

只有当 skill 被选中后才加载：

- 详细 prompt 约束
- 执行步骤
- 调用限制
- 适用边界

用途：

- 给某个具体节点或子图提供执行细则

#### 第三层：Resource Layer

只有真正执行该 skill 时才加载：

- 外部文件
- 参考模板
- 补充规则
- 额外 adapter 配置

用途：

- 避免上下文爆炸
- 让 resource 成为按需装载资产

### 6.5 Skill 在 Graph 中的挂载方式

skill 不应再只是 prompt 附件，而应成为 graph 可消费的能力对象。

每个 skill 至少要声明：

- `skill_id`
- `metadata`
- `selection_rules`
- `required_context_keys`
- `input_schema`
- `output_schema`
- `instruction_loader`
- `resource_loader`
- `adapter_hooks`

这样 graph 才能决定：

- 是否选它
- 何时加载到 instruction 层
- 是否需要额外 resources
- 输出如何接回统一 state

### 6.6 Context Budget 管理

context engineering 如果不做预算控制，最后一定退化成“堆 prompt”。

因此必须引入 `context_budget_manager`，至少管理：

- 总 token 预算
- system / developer 固定预算
- memory 预算
- skill metadata 预算
- skill instruction 预算
- recent history 预算

基本策略：

- 优先保留 system、developer、permission
- memory facts 优先于 memory prose
- selected skill instruction 优先于未选 skill metadata
- 最近 session history 采用窗口与摘要混合策略

### 6.7 Session 装配产物

session bootstrap 完成后，应产出统一的 `ContextEnvelope`，至少包含：

- `system_blocks`
- `developer_blocks`
- `permission_blocks`
- `memory_facts`
- `memory_summary`
- `skill_blocks`
- `recent_messages`
- `current_message`
- `budget_report`
- `assembly_trace`

这样后续 graph 节点不再自己拼 prompt，而是从 `ContextEnvelope` 中读取自己需要的受控片段。

### 6.8 Context Engineering 的测试重点

这部分后续写实施计划时，必须优先做测试。

重点测试：

- session 注入顺序测试
- context budget 截断策略测试
- selected skill 才会触发 instruction/resource 加载的测试
- memory facts 与 summary 同时存在时的优先级测试
- permission 缺失时的拒绝执行测试
- 同一输入在固定上下文下生成稳定 `ContextEnvelope` 的快照测试

## 7. 待继续展开的设计段落

- LangSmith 与 Langfuse 的观测设计
- 内部函数、工具与 graph node 的映射方式
- TDD 驱动的重构实施计划
- 最终落地为正式实现 plan

## 8. LangSmith 与 Langfuse 双观测设计

这次后端重构不能把观测当成“后续再补的基础设施”。因为新的核心就是 graph 编排、结构化输出、context engineering 和 skill 渐进加载，这些能力如果没有可观测性，出问题时几乎无法定位。

因此需要把 `LangSmith` 和 `Langfuse` 分工明确地接入运行时，而不是二选一。

### 8.1 角色分工

#### LangSmith

主职责：

- graph 级 trace
- node 执行链路追踪
- state transition 调试
- 节点输入输出快照
- 错误路径分析
- 重试与 fallback 路由分析

适合回答的问题：

- 这次请求走了哪条 graph 路径
- 哪个 node 产出了非法 schema
- 哪个并行分支变慢了
- 哪次 retry 是因为 validation fail，哪次是因为 tool fail

#### Langfuse

主职责：

- prompt 输入输出监控
- 模型调用日志
- prompt 版本管理
- prompt 成本、延迟、质量分析
- prompt 级别回放与对比

适合回答的问题：

- 当前节点到底喂给模型了什么 prompt
- 哪个 prompt 版本导致输出质量下降
- 哪次 structured output 经常漏字段
- 哪个模型在某类任务上成本过高或稳定性差

结论：

- `LangSmith` 负责看“图是怎么跑的”
- `Langfuse` 负责看“模型到底吃了什么、吐了什么”

### 8.2 统一关联键

两套系统必须通过统一关联键打通，否则排障时会分裂成两份日志。

建议统一携带：

- `correlation_id`
- `session_id`
- `user_id`
- `request_id`
- `graph_run_id`
- `node_run_id`
- `prompt_run_id`
- `schema_version`
- `model_provider`
- `model_name`

要求：

- 每个 API 请求进来立即生成 `correlation_id`
- graph 运行期所有 node 都继承同一 `correlation_id`
- 每次 LLM 调用生成独立 `prompt_run_id`
- `prompt_run_id` 要可回连到 `node_run_id`

### 8.3 LangSmith 采集范围

每个 graph node 至少记录：

- node 名称
- 开始时间 / 结束时间
- 输入 schema 名称与版本
- 输出 schema 名称与版本
- 输入摘要
- 输出摘要
- retry 次数
- fallback 是否触发
- 错误类型
- 上下游 node 关系

特别需要记录的事件：

- `ContextEnvelope` 组装完成
- `SkillSelection` 完成
- `ExecutionPlan` 完成
- 并行分支 fan-out
- 并行分支 join
- schema validation failure
- response render 完成
- memory writeback 提交

注意：

- LangSmith 中记录的是“足够调试 graph 的结构化摘要”
- 不应把完整敏感原文无限制展开

### 8.4 Langfuse 采集范围

每次模型调用至少记录：

- prompt 模板标识
- prompt 版本
- system / developer / memory / skill blocks 的组成摘要
- 最终发送给模型的 messages 或 structured prompt
- `response_format` 或 schema 名称
- 模型原始输出
- schema 校验结果
- token 使用量
- 调用延迟
- provider / model / temperature

特别要追踪的 prompt 类型：

- `parse_user_intent`
- `select_skills`
- `build_execution_plan`
- `run_memory_reasoning`
- `synthesize_decision`
- `render_response`

因为这些节点最容易发生 prompt 漂移或结构化字段缺失。

### 8.5 失败排查路径

有了双观测之后，排查流程应该是固定的：

1. 先在 LangSmith 看 graph 路径与失败节点
2. 锁定失败 node 的 `node_run_id`
3. 通过关联键跳到 Langfuse 看该 node 对应 prompt 输入输出
4. 判断问题属于：
   - context 组装错误
   - prompt 约束不足
   - schema 定义不合理
   - 模型输出不稳定
   - tool / repository 数据异常
5. 如果是结构化输出异常，再回到 LangSmith 看 fallback 和 retry 是否按设计生效

这样排障链路才完整。

### 8.6 必须观测的失败类型

必须单独打点的失败类型：

- `schema_validation_error`
- `prompt_assembly_error`
- `skill_load_error`
- `context_budget_overflow`
- `tool_execution_error`
- `datasource_timeout`
- `fallback_triggered`
- `retry_exhausted`
- `memory_writeback_error`
- `response_render_error`

这些类型要统一为枚举，避免日志里出现无法统计的自由文本。

### 8.7 Prompt 版本化

既然 `Langfuse` 要负责 prompt 监控，那么 prompt 本身必须版本化。

每个关键 prompt 都要带：

- `prompt_name`
- `prompt_version`
- `owner_node`
- `expected_schema`
- `last_updated_at`

建议把 prompt 版本与 schema 版本一起记录。否则会出现：

- prompt 升级了，但 schema 没升级
- schema 升级了，但 downstream adapter 没同步

这会直接导致结构化输出漂移。

## 9. 内部函数、工具与 Graph Node 的映射

你特别强调“调用内部函数这些也都需要编排”。这意味着内部函数不能继续像现在一样散落在 service 里互相调用，而要纳入统一执行模型。

原则上，内部函数不是天然等于 graph node，但所有重要内部函数都必须被 graph 控制。

### 9.1 三类执行单元

建议把后端执行单元分为三类：

#### 第一类：Graph Node

适合：

- 会影响流程路由
- 会生成新的结构化中间状态
- 会触发并行 / 串行边界
- 会调用 LLM
- 会影响最终用户响应

例如：

- `parse_user_intent`
- `select_skills`
- `build_execution_plan`
- `synthesize_decision`

#### 第二类：Node-local Step

适合：

- 不需要独立 trace 路由
- 只是某个 node 内部的确定性步骤
- 输入输出都由当前 node 完全拥有

例如：

- 规范化机场代码
- 清洗日期范围
- 合并同一航班的不同平台价格

这类步骤不单独成为 graph node，但仍要在 node 内受控执行，并可选择做细粒度 span。

#### 第三类：Tool / Repository Call

适合：

- 外部数据源访问
- 数据库存取
- Redis 读写
- 纯计算工具

例如：

- 查询携程数据源
- 获取用户 memory rows
- 计算偏好匹配分数
- 生成值得买 signals

这些调用不直接拥有流程决定权，但必须在 graph node 内被受控调用。

### 9.2 判断何时升级为 Graph Node

一个内部函数如果满足任意两项，就应优先升级为 graph node：

- 输出会被多个下游模块复用
- 输出需要结构化校验
- 失败后需要单独 retry 或 fallback
- 性能上需要单独观测
- 将来可能替换实现方式
- 会显著影响最终推荐结论

例如：

- `memory reasoning` 需要独立升级为 node
- `skill selection` 必须是 node
- `flight search aggregation` 可以视复杂度拆成 node 或保留在 node 内部

### 9.3 现有后端模块的重映射建议

当前已有模块不应直接搬过去，而应重新映射：

- `agents/intention_agent.py`
  - 拆分为 `parse_user_intent` 与部分 `build_execution_plan`
- `agents/orchestration_agent.py`
  - 完全被 `LangGraph` 替代
- `services/search_service.py`
  - 拆入 `run_flight_search`、adapter、response assembly
- `services/memory_service.py`
  - 拆入 `hydrate_memory_context`、`schedule_memory_writeback`、memory repositories
- `skills/*/agent.py`
  - 重构为 skill capability + instruction/resource loaders + adapter hooks
- `tools/*.py`
  - 保留为 tool 层，但统一通过 graph node 调用

### 9.4 Tool 调用约束

为了避免“graph 只是外壳，逻辑仍在 service 里乱跑”，必须明确：

- tool 不允许直接调用 graph
- tool 不允许直接组装 prompt
- tool 不允许写入最终 response
- tool 不允许持有跨节点状态
- repository 不允许决定流程分支

tool 的职责只能是：

- 拿到明确输入
- 执行确定性逻辑
- 返回结构化结果

### 9.5 Node 与 Tool 的契约边界

建议约束如下：

- graph node 负责“决定要不要做”
- tool 负责“怎么把这件确定性工作做完”

例如：

- `run_flight_search` node 决定需要查哪些数据源、是否并发、失败是否降级
- `ctrip_source` / `compare_prices` / `generate_signals` 负责具体执行

这样可以保证：

- 流程控制可追踪
- 业务工具可复用
- 失败策略统一归于 graph

### 9.6 需要显式编排的内部函数类型

下面这几类内部函数必须进入统一编排视角：

- context assembly 相关函数
- skill selection 与 loading 相关函数
- memory summary / memory facts 组装函数
- flight search 聚合与归一化函数
- preference scoring 与 signal generation 函数
- decision synthesis 相关函数
- response render 与 DTO 装配函数

即使这些函数不全部成为独立 graph node，也必须从“service 内部随便调用”改成“由 graph node 显式拥有和调度”。

## 10. 待继续展开的设计段落

- TDD 驱动的重构实施计划
- 最终落地为正式实现计划文件

## 11. TDD 驱动的重构实施计划

这一部分开始从“设计”收束为“可执行重构计划”。由于你要求后端整体切换到新架构，而不是与旧架构长期并存，所以计划必须满足两个条件：

- 每一阶段都能通过测试证明当前重构是可用的
- 每一阶段都在为最终直接切换主链路做准备，而不是做无效过渡层

整体原则：

- 先立契约，再立 graph
- 先立可验证的 context pipeline，再接业务节点
- 先把观测与错误语义接好，再放大执行面
- 旧代码只作为迁移参考，不作为新架构的长期兼容层

### 11.1 总体阶段

建议按 8 个阶段推进：

1. 建立 contracts 与测试骨架
2. 建立 session bootstrap 与 context engineering
3. 建立 graph runtime 与基础节点
4. 接入 flight search / preference / memory 三个并行分支
5. 建立 decision synthesis 与 response render
6. 接入 progressive skill loading
7. 接入 LangSmith / Langfuse 双观测
8. 切换 API 主链路并移除旧编排入口

### 11.2 阶段 1：建立 Contracts 与测试骨架

目标：

- 先把新后端的“语言”定义清楚
- 让后续所有 graph node 都有稳定 schema 可依赖

先写测试：

- `backend/tests/contracts/test_workflow_contracts.py`
  - 校验 `WorkflowState` 基本结构完整
  - 校验 `WorkflowRequest` 必填字段
  - 校验 `WorkflowError` 枚举值合法
- `backend/tests/contracts/test_intent_contracts.py`
  - 校验 `NormalizedIntent` 可以表示预算、日期范围、约束、歧义
  - 缺失关键字段时应失败
- `backend/tests/contracts/test_decision_contracts.py`
  - 校验 `DecisionResult`、`DecisionSignal`、`FrontendResponse`
- `backend/tests/contracts/test_schema_versioning.py`
  - 关键 schema 必须带版本字段

再实现：

- 新建 `backend/application/contracts/`
- 定义所有核心 Pydantic 模型
- 定义统一错误枚举与版本字段

完成标志：

- 所有 contract 测试通过
- 新后端目录下不再依赖旧 `schemas/` 作为 graph 内部契约

### 11.3 阶段 2：建立 Session Bootstrap 与 Context Engineering

目标：

- 在任何业务节点执行前，先让上下文装配可测试、可重复、可观测

先写测试：

- `backend/tests/context/test_context_envelope.py`
  - 校验 `ContextEnvelope` 结构完整
- `backend/tests/context/test_context_ordering.py`
  - 校验注入顺序固定为：
    - system
    - developer
    - permissions
    - memory facts
    - long-term summary
    - recent history
    - skill metadata
    - current user message
- `backend/tests/context/test_context_budget.py`
  - 超预算时应按策略裁剪
- `backend/tests/context/test_permission_injection.py`
  - 缺少 permission block 时不得进入可执行状态
- `backend/tests/context/test_skill_metadata_loading.py`
  - 默认只加载 skill metadata，不加载 instruction 与 resources

再实现：

- `backend/application/context/assembler.py`
- `backend/application/context/budget.py`
- `backend/application/context/permissions.py`
- `backend/application/context/memory_adapter.py`
- `backend/application/context/skill_adapter.py`

完成标志：

- 输入同一个 request + memory + skill registry 时，能稳定生成同一个 `ContextEnvelope`
- 所有装配顺序和预算策略都有测试覆盖

### 11.4 阶段 3：建立 Graph Runtime 与基础节点

目标：

- 把“后端主链路由 graph 驱动”这件事先跑起来
- 暂时不接全部业务逻辑，只先把骨架和 typed state 跑通

先写测试：

- `backend/tests/graph/test_graph_bootstrap.py`
  - graph 可初始化
  - 初始 state 合法
- `backend/tests/graph/test_graph_routing.py`
  - 基础节点按预期顺序执行
- `backend/tests/graph/test_graph_state_transitions.py`
  - 每个节点都会更新正确的 state 字段
- `backend/tests/graph/test_graph_error_handling.py`
  - 节点报错时能生成 `WorkflowError`

再实现：

- `backend/application/graph/state.py`
- `backend/application/graph/nodes/bootstrap_session_context.py`
- `backend/application/graph/nodes/parse_user_intent.py`
- `backend/application/graph/nodes/hydrate_memory_context.py`
- `backend/application/graph/nodes/select_skills.py`
- `backend/application/graph/nodes/build_execution_plan.py`
- `backend/application/graph/runtime.py`
- `backend/application/graph/factory.py`

完成标志：

- graph 能在 fake data 下完整跑通到 `workflow_plan`
- 老的 `orchestration_agent.py` 不再承担新主链路职责

### 11.5 阶段 4：接入并行业务分支

目标：

- 把核心业务模块接入 graph，并完成并行执行

先写测试：

- `backend/tests/graph/test_parallel_fanout.py`
  - `run_flight_search`、`run_preference_match`、`run_memory_reasoning` 并行触发
- `backend/tests/graph/test_parallel_join.py`
  - 三个分支结果可正确 join
- `backend/tests/search/test_flight_search_node.py`
  - flight search node 输出 `FlightSearchResult`
- `backend/tests/preference/test_preference_match_node.py`
  - 偏好匹配输出结构稳定
- `backend/tests/memory/test_memory_reasoning_node.py`
  - 记忆推理输出结构稳定

再实现：

- `backend/application/graph/nodes/run_flight_search.py`
- `backend/application/graph/nodes/run_preference_match.py`
- `backend/application/graph/nodes/run_memory_reasoning.py`
- `backend/application/adapters/intent_to_search.py`
- `backend/application/adapters/search_to_preference.py`
- `backend/application/adapters/memory_to_prompt.py`

完成标志：

- 三个分支都通过统一 contract 输出
- graph 能在并行分支完成后稳定汇总状态

### 11.6 阶段 5：建立 Decision Synthesis 与 Response Render

目标：

- 让 graph 从中间产物走到最终用户可消费响应

先写测试：

- `backend/tests/decision/test_decision_synthesis_node.py`
  - 基于 search / preference / memory 结果生成 `DecisionResult`
- `backend/tests/decision/test_reasoning_artifacts.py`
  - `decision_factors`、`rejected_candidates`、`branch_reason` 字段齐全
- `backend/tests/response/test_response_render_node.py`
  - `DecisionResult` 能转成 `FrontendResponse`
- `backend/tests/response/test_response_adapter.py`
  - DTO 字段符合前端预期

再实现：

- `backend/application/graph/nodes/synthesize_decision.py`
- `backend/application/graph/nodes/render_response.py`
- `backend/application/adapters/decision_to_frontend.py`

完成标志：

- graph 能生成结构化最终响应
- 前端需要的字段不再依赖旧 service 拼装

### 11.7 阶段 6：接入 Skill 渐进加载

目标：

- 把 skill 从“文档式 prompt 附件”重构为 graph 可选择、可延迟加载的能力对象

先写测试：

- `backend/tests/skills/test_skill_registry_v2.py`
  - skill metadata 可枚举
- `backend/tests/skills/test_skill_selection.py`
  - 给定意图和 context，可选出预期 skill
- `backend/tests/skills/test_progressive_loading.py`
  - 未选中 skill 不加载 instruction / resource
- `backend/tests/skills/test_skill_context_injection.py`
  - 选中 skill 后可正确注入 context block

再实现：

- `backend/application/skills/registry.py`
- `backend/application/skills/models.py`
- `backend/application/skills/loaders.py`
- `backend/application/adapters/skill_selection_to_context.py`

完成标志：

- skill loading 由 graph 决定，不再由节点随意读取文件
- context budget 能感知 skill instruction / resource 成本

### 11.8 阶段 7：接入 LangSmith / Langfuse 双观测

目标：

- 让新后端从一开始就是可排障系统，而不是“先跑起来再说”

先写测试：

- `backend/tests/observability/test_trace_context.py`
  - `correlation_id` 在 graph 与 prompt 调用间可贯通
- `backend/tests/observability/test_langsmith_events.py`
  - 节点执行会产生预期 trace event
- `backend/tests/observability/test_langfuse_prompt_logging.py`
  - prompt 调用会记录版本、输入、输出、schema
- `backend/tests/observability/test_validation_failure_logging.py`
  - schema 校验失败会同时进入 LangSmith / Langfuse

再实现：

- `backend/infrastructure/observability/context.py`
- `backend/infrastructure/observability/langsmith.py`
- `backend/infrastructure/observability/langfuse.py`
- `backend/infrastructure/observability/events.py`

完成标志：

- 任一失败请求都能从 graph trace 跳到 prompt log
- 关键失败类型具备统一枚举和统计能力

### 11.9 阶段 8：切换 API 主链路并移除旧编排入口

目标：

- 让 `/api/search`、后续 `/api/chat` 等主入口正式切到 graph runtime
- 旧编排入口退役

先写测试：

- `backend/tests/api/test_search_api_graph_runtime.py`
  - `/api/search` 走新 graph runtime
- `backend/tests/api/test_chat_api_graph_runtime.py`
  - `/api/chat` 如存在，走新 graph runtime
- `backend/tests/e2e/test_graph_runtime_e2e.py`
  - 从请求进入到最终响应完整通过
- `backend/tests/e2e/test_memory_writeback_e2e.py`
  - 响应完成后异步记忆写回生效

再实现：

- 修改 `backend/api/search.py`
- 修改 `backend/api/chat.py`（如存在）
- 移除对旧 `services/*` 编排路径的依赖
- 将旧 `agents/*` 保留为迁移参考，最终在确认无引用后删除

完成标志：

- API 主链路完全走 graph runtime
- 旧 `orchestration_agent.py` 与旧 service 编排路径无生产入口引用

## 12. 文件级重构建议

为了避免“边改边散”，建议按新目录明确落位：

- 新建：`backend/application/contracts/`
- 新建：`backend/application/context/`
- 新建：`backend/application/graph/`
- 新建：`backend/application/adapters/`
- 新建：`backend/application/skills/`
- 新建：`backend/infrastructure/observability/`
- 保留并重用：`backend/tools/`
- 保留并重构边界：`backend/memory/`
- 保留并逐步替换：`backend/data_sources/`
- 最后退役：`backend/agents/`、旧 `backend/services/` 编排逻辑

## 13. 验收标准

后端重构完成的验收标准应至少包括：

- 所有主链路由 `LangGraph` 驱动，不再依赖旧 orchestration agent
- session 注入顺序固定且有测试覆盖
- skills 支持 metadata -> instruction -> resource 渐进加载
- 关键 LLM 节点全部具备结构化输出校验
- 并行分支、join、retry、fallback 都可在 LangSmith 中追踪
- prompt 版本、输入输出、schema 校验结果都可在 Langfuse 中查看
- 内部函数调用已纳入 graph 控制边界
- `/api/search` 主链路通过新 runtime 完成端到端请求

## 14. 下一步输出

这份文档目前已经完成了“后端重构设计 + 分阶段实施策略”。下一步应把它进一步收束为正式的 implementation plan，要求：

- 每个阶段进一步拆成可执行任务
- 每个任务都按 TDD 写明先写什么 failing test
- 明确每个任务要改哪些文件
- 明确每个任务的完成判定

这一步可以继续生成一份更细的执行计划，作为真正开始编码时的操作清单。

## 15. 细化任务清单

这一节把前面的阶段计划继续细化为“可直接执行”的任务清单。这里仍然遵循 TDD 原则：

- 先写 failing test
- 明确预期失败原因
- 写最小实现使其通过
- 跑局部测试
- 再进入下一任务

### 15.1 阶段 1 任务清单：Contracts 与测试骨架

#### 任务 1.1：建立 contracts 目录与基础模型入口

**涉及文件：**

- 新建 `backend/application/contracts/__init__.py`
- 新建 `backend/application/contracts/base.py`
- 新建 `backend/tests/contracts/test_contract_imports.py`

**先写测试：**

- `test_contract_imports.py`
  - 可以从 `backend.application.contracts` 导入基础模型
  - 缺失模块时应直接失败

**实现内容：**

- 定义基础 `BaseContractModel`
- 定义共享配置，例如严格字段校验、禁止额外字段

**完成判定：**

- 合约模块可正常导入
- 合约基类对未知字段默认报错

#### 任务 1.2：定义 `WorkflowRequest` / `WorkflowError`

**涉及文件：**

- 新建 `backend/application/contracts/workflow.py`
- 新建 `backend/tests/contracts/test_workflow_contracts.py`

**先写测试：**

- 合法请求可通过校验
- 缺少 `user_id`、`session_id` 或 `message` 时失败
- `WorkflowError` 只允许受控错误码

**实现内容：**

- `WorkflowRequest`
- `WorkflowErrorCode`
- `WorkflowError`

**完成判定：**

- graph 初始输入已具备统一入口模型

#### 任务 1.3：定义 `SessionContext` / `ContextEnvelope`

**涉及文件：**

- 新建 `backend/application/contracts/session.py`
- 新建 `backend/tests/contracts/test_session_contracts.py`

**先写测试：**

- `ContextEnvelope` 包含固定 block 字段
- 缺失 `current_message` 或 `budget_report` 时失败

**实现内容：**

- `SessionContext`
- `ContextEnvelope`
- `BudgetReport`

**完成判定：**

- 后续 context assembler 有稳定目标输出结构

#### 任务 1.4：定义 `NormalizedIntent`

**涉及文件：**

- 新建 `backend/application/contracts/intent.py`
- 新建 `backend/tests/contracts/test_intent_contracts.py`

**先写测试：**

- 预算、日期区间、约束、歧义字段均可表达
- 非法日期区间失败
- 非法约束类型失败

**实现内容：**

- `LocationRef`
- `DateWindow`
- `IntentConstraint`
- `NormalizedIntent`

**完成判定：**

- 意图解析节点后续无需依赖自由文本约定

#### 任务 1.5：定义 `MemoryContext` / `SkillSelection` / `ExecutionPlan`

**涉及文件：**

- 新建 `backend/application/contracts/memory.py`
- 新建 `backend/application/contracts/skills.py`
- 新建 `backend/tests/contracts/test_memory_skill_plan_contracts.py`

**先写测试：**

- `MemoryContext` 可同时表达 facts 与 summary
- `SkillSelection` 可表达 selected skills 与 load plan
- `ExecutionPlan` 可表达并行分支与 fallback

**实现内容：**

- `MemoryFact`
- `MemoryContext`
- `SelectedSkill`
- `SkillSelection`
- `ExecutionPlan`

**完成判定：**

- graph 中段状态具备统一 contract

#### 任务 1.6：定义搜索、偏好、决策、响应契约

**涉及文件：**

- 新建 `backend/application/contracts/search.py`
- 新建 `backend/application/contracts/preference.py`
- 新建 `backend/application/contracts/decision.py`
- 新建 `backend/application/contracts/response.py`
- 新建 `backend/tests/contracts/test_decision_response_contracts.py`

**先写测试：**

- `FlightCandidate`、`FlightSearchResult` 校验通过
- `PreferenceMatchResult` 可表达命中与冲突
- `DecisionResult` 含 reasoning artifacts
- `FrontendResponse` 可表达前端卡片和 recommendation

**实现内容：**

- 各类核心结果模型
- `schema_name` / `schema_version` 通用字段

**完成判定：**

- 所有关键输出模型齐备

### 15.2 阶段 2 任务清单：Context Engineering

#### 任务 2.1：建立 context 模块骨架

**涉及文件：**

- 新建 `backend/application/context/__init__.py`
- 新建 `backend/application/context/assembler.py`
- 新建 `backend/application/context/budget.py`
- 新建 `backend/tests/context/test_context_imports.py`

**先写测试：**

- context 模块可正常导入
- assembler 提供统一入口函数

**实现内容：**

- `assemble_context_envelope(...)`
- `ContextBudgetManager`

**完成判定：**

- context 层具备可注入入口

#### 任务 2.2：固定 session 注入顺序

**涉及文件：**

- 修改 `backend/application/context/assembler.py`
- 新建 `backend/tests/context/test_context_ordering.py`

**先写测试：**

- 输出 block 顺序严格为：
  - system
  - developer
  - permissions
  - memory facts
  - long-term summary
  - recent history
  - skill metadata
  - current message

**实现内容：**

- 将 block 组装流程显式化
- 为 `assembly_trace` 记录顺序

**完成判定：**

- 顺序偏移会导致测试直接失败

#### 任务 2.3：实现 context budget 裁剪

**涉及文件：**

- 修改 `backend/application/context/budget.py`
- 新建 `backend/tests/context/test_context_budget.py`

**先写测试：**

- 超预算时优先保留 system / developer / permission
- memory facts 优先于 memory prose
- 未选中 skill metadata 先被裁剪

**实现内容：**

- token 预算策略
- block 级优先级定义

**完成判定：**

- 裁剪行为稳定且可预测

#### 任务 2.4：实现 permission 与 memory 注入

**涉及文件：**

- 新建 `backend/application/context/permissions.py`
- 新建 `backend/application/context/memory_adapter.py`
- 新建 `backend/tests/context/test_permission_injection.py`
- 新建 `backend/tests/context/test_memory_context_blocks.py`

**先写测试：**

- 缺少 permission 时 assembler 失败
- memory facts 与 summary 同时存在时可正确区分

**实现内容：**

- permission blocks
- memory facts blocks
- long-term summary blocks

**完成判定：**

- context envelope 已具备真实运行所需信息

#### 任务 2.5：实现 skill metadata 注入

**涉及文件：**

- 新建 `backend/application/context/skill_adapter.py`
- 新建 `backend/tests/context/test_skill_metadata_loading.py`

**先写测试：**

- 默认仅加载 metadata
- 未选中 skill 不加载 instruction / resource

**实现内容：**

- 将 skill registry 输出转为 context blocks

**完成判定：**

- assembler 与 skills 层完成第一处接缝

### 15.3 阶段 3 任务清单：Graph Runtime 骨架

#### 任务 3.1：定义 graph state

**涉及文件：**

- 新建 `backend/application/graph/state.py`
- 新建 `backend/tests/graph/test_graph_state.py`

**先写测试：**

- state 初始字段齐全
- state 更新时不允许未声明字段混入

**实现内容：**

- `WorkflowState`
- state merge/update 规则

**完成判定：**

- graph 有统一运行时状态模型

#### 任务 3.2：建立 graph factory 与 runtime

**涉及文件：**

- 新建 `backend/application/graph/factory.py`
- 新建 `backend/application/graph/runtime.py`
- 新建 `backend/tests/graph/test_graph_bootstrap.py`

**先写测试：**

- graph 可初始化
- graph 可接收 `WorkflowRequest`

**实现内容：**

- graph factory
- runtime invoke 入口

**完成判定：**

- graph 可从 request 跑到基础节点结束

#### 任务 3.3：实现基础节点

**涉及文件：**

- 新建 `backend/application/graph/nodes/bootstrap_session_context.py`
- 新建 `backend/application/graph/nodes/parse_user_intent.py`
- 新建 `backend/application/graph/nodes/hydrate_memory_context.py`
- 新建 `backend/application/graph/nodes/select_skills.py`
- 新建 `backend/application/graph/nodes/build_execution_plan.py`
- 新建对应测试文件

**先写测试：**

- 每个节点仅更新自己的目标字段
- 节点失败时输出 `WorkflowError`
- `build_execution_plan` 输出并行分支定义

**实现内容：**

- 基础 node 函数
- node metadata，例如 retryable、schema refs

**完成判定：**

- graph 能稳定跑到并行分支入口

### 15.4 阶段 4 任务清单：并行业务分支

#### 任务 4.1：接入 `run_flight_search`

**涉及文件：**

- 新建 `backend/application/graph/nodes/run_flight_search.py`
- 新建 `backend/application/adapters/intent_to_search.py`
- 新建 `backend/tests/search/test_flight_search_node.py`

**先写测试：**

- 合法 intent 可转为 datasource 查询参数
- 输出必须为 `FlightSearchResult`

**实现内容：**

- 连接现有 `data_sources/` 与 `tools/`
- 归一化候选结果

**完成判定：**

- graph 查价分支可独立通过测试

#### 任务 4.2：接入 `run_preference_match`

**涉及文件：**

- 新建 `backend/application/graph/nodes/run_preference_match.py`
- 新建 `backend/application/adapters/search_to_preference.py`
- 新建 `backend/tests/preference/test_preference_match_node.py`

**先写测试：**

- 候选航班可转为偏好评分输入
- 输出包括命中偏好与冲突偏好

**实现内容：**

- 连接现有 `tools/match_preference.py`

**完成判定：**

- 偏好分支 contract 稳定

#### 任务 4.3：接入 `run_memory_reasoning`

**涉及文件：**

- 新建 `backend/application/graph/nodes/run_memory_reasoning.py`
- 新建 `backend/application/adapters/memory_to_prompt.py`
- 新建 `backend/tests/memory/test_memory_reasoning_node.py`

**先写测试：**

- memory facts 能转为 prompt-safe reasoning input
- 输出包含 decision-relevant anchors

**实现内容：**

- 连接现有 `memory/` 层

**完成判定：**

- 记忆推理分支不再只是“附加 prompt 文本”

#### 任务 4.4：实现并行 fan-out / join

**涉及文件：**

- 修改 `backend/application/graph/factory.py`
- 新建 `backend/tests/graph/test_parallel_fanout.py`
- 新建 `backend/tests/graph/test_parallel_join.py`

**先写测试：**

- 三个分支可并行执行
- join 后状态完整

**实现内容：**

- graph 并行边与 join 逻辑

**完成判定：**

- 主业务计算路径跑通

### 15.5 阶段 5 任务清单：Decision 与 Response

#### 任务 5.1：实现 `synthesize_decision`

**涉及文件：**

- 新建 `backend/application/graph/nodes/synthesize_decision.py`
- 新建 `backend/tests/decision/test_decision_synthesis_node.py`
- 新建 `backend/tests/decision/test_reasoning_artifacts.py`

**先写测试：**

- 能根据并行分支结果生成 `DecisionResult`
- 必须包含 `decision_factors`、`branch_reason`、`confidence_explanation`

**实现内容：**

- 决策综合逻辑
- reasoning artifacts 生成逻辑

**完成判定：**

- 可解释决策产物形成

#### 任务 5.2：实现 `render_response`

**涉及文件：**

- 新建 `backend/application/graph/nodes/render_response.py`
- 新建 `backend/application/adapters/decision_to_frontend.py`
- 新建 `backend/tests/response/test_response_render_node.py`

**先写测试：**

- `DecisionResult` 能转为 `FrontendResponse`
- DTO 字段满足前端消费要求

**实现内容：**

- 最终响应组装
- SSE / 非流式响应适配

**完成判定：**

- graph 已能产生最终 API payload

### 15.6 阶段 6 任务清单：Skill 渐进加载

#### 任务 6.1：建立 skill registry v2

**涉及文件：**

- 新建 `backend/application/skills/registry.py`
- 新建 `backend/application/skills/models.py`
- 新建 `backend/tests/skills/test_skill_registry_v2.py`

**先写测试：**

- skill metadata 可枚举
- skill 声明 input/output schema refs

**实现内容：**

- `SkillDefinition`
- `SkillMetadata`

**完成判定：**

- graph 可消费技能元数据

#### 任务 6.2：实现 progressive loaders

**涉及文件：**

- 新建 `backend/application/skills/loaders.py`
- 新建 `backend/tests/skills/test_progressive_loading.py`

**先写测试：**

- 默认只加载 metadata
- 选中后才加载 instruction
- 执行前才加载 resource

**实现内容：**

- metadata loader
- instruction loader
- resource loader

**完成判定：**

- skill 渐进式披露真实可运行

#### 任务 6.3：将 skill 注入 graph

**涉及文件：**

- 新建 `backend/application/adapters/skill_selection_to_context.py`
- 修改 `backend/application/graph/nodes/select_skills.py`
- 新建 `backend/tests/skills/test_skill_context_injection.py`

**先写测试：**

- 选中 skill 后可注入正确 context blocks
- 未选中 skill 不应污染 context

**实现内容：**

- skill context 与 graph state 对接

**完成判定：**

- skill 从“外挂说明”变成 graph 内正式能力

### 15.7 阶段 7 任务清单：双观测接入

#### 任务 7.1：贯通 trace context

**涉及文件：**

- 新建 `backend/infrastructure/observability/context.py`
- 新建 `backend/tests/observability/test_trace_context.py`

**先写测试：**

- `correlation_id`、`node_run_id`、`prompt_run_id` 可贯通

**实现内容：**

- trace context 对象
- graph / llm 调用共享上下文

**完成判定：**

- 观测系统具备统一关联键

#### 任务 7.2：接入 LangSmith

**涉及文件：**

- 新建 `backend/infrastructure/observability/langsmith.py`
- 新建 `backend/tests/observability/test_langsmith_events.py`

**先写测试：**

- 节点执行能产出预期 trace event

**实现内容：**

- node 生命周期 trace hooks
- error / fallback 事件上报

**完成判定：**

- graph 调试链路成型

#### 任务 7.3：接入 Langfuse

**涉及文件：**

- 新建 `backend/infrastructure/observability/langfuse.py`
- 新建 `backend/tests/observability/test_langfuse_prompt_logging.py`

**先写测试：**

- prompt 版本、输入、输出、schema 名称被记录

**实现内容：**

- prompt logging wrapper
- llm invocation instrumentation

**完成判定：**

- prompt 级监控成型

#### 任务 7.4：统一失败打点

**涉及文件：**

- 新建 `backend/infrastructure/observability/events.py`
- 新建 `backend/tests/observability/test_validation_failure_logging.py`

**先写测试：**

- `schema_validation_error` 等关键失败统一枚举

**实现内容：**

- 失败事件模型
- 双平台统一打点逻辑

**完成判定：**

- 结构化失败可被稳定统计

### 15.8 阶段 8 任务清单：API 切换与旧编排退役

#### 任务 8.1：切换 `/api/search` 到 graph runtime

**涉及文件：**

- 修改 `backend/api/search.py`
- 新建 `backend/tests/api/test_search_api_graph_runtime.py`

**先写测试：**

- `/api/search` 请求进入新 runtime
- 返回 `FrontendResponse`

**实现内容：**

- 用 graph runtime 替换旧 service 编排调用

**完成判定：**

- search 主链路已切换

#### 任务 8.2：切换 `/api/chat` 或其他相关入口

**涉及文件：**

- 修改 `backend/api/chat.py`（如存在）
- 新建 `backend/tests/api/test_chat_api_graph_runtime.py`

**先写测试：**

- chat 类请求进入新 runtime

**实现内容：**

- 接口入口统一走 graph

**完成判定：**

- 交互类主入口不再依赖旧编排

#### 任务 8.3：补端到端测试

**涉及文件：**

- 新建 `backend/tests/e2e/test_graph_runtime_e2e.py`
- 新建 `backend/tests/e2e/test_memory_writeback_e2e.py`

**先写测试：**

- 请求从进入到响应完整跑通
- 响应后异步写回记忆成功

**实现内容：**

- 必要的 e2e fixture 与 stub

**完成判定：**

- 新后端主链路端到端可验证

#### 任务 8.4：移除旧编排入口引用

**涉及文件：**

- 清理 `backend/agents/` 的主链路引用
- 清理旧 `backend/services/` 编排引用
- 新建 `backend/tests/api/test_no_legacy_orchestration_refs.py`

**先写测试：**

- API 主链路不再 import 旧 orchestration 入口

**实现内容：**

- 删除或退役旧编排路径

**完成判定：**

- 旧运行时彻底退出生产主链路

## 16. 推荐执行顺序

如果要直接进入编码，建议按下面的最小闭环顺序推进：

1. 完成阶段 1 全部 contracts
2. 完成阶段 2 的 context envelope 与 budget
3. 完成阶段 3 的 graph runtime 与基础节点
4. 只先接 `run_flight_search`，跑通最小业务闭环
5. 再接 `run_preference_match` 与 `run_memory_reasoning`
6. 再接 `synthesize_decision` 与 `render_response`
7. 最后接 skills、observability、API 切换

这样做的原因是：

- 先把“骨架”和“语言”定住
- 再把最短业务路径跑通
- 避免一开始同时改 graph、skills、observability，导致定位成本失控

## 17. 编码启动建议

真正开始编码时，建议以这 3 个任务作为第一批切入点：

1. `任务 1.2：定义 WorkflowRequest / WorkflowError`
2. `任务 1.3：定义 SessionContext / ContextEnvelope`
3. `任务 3.1：定义 graph state`

这是最小可行起点，因为：

- 没有入口 contract，就无法稳定定义 graph runtime
- 没有 `ContextEnvelope`，后续 context engineering 会反复返工
- 没有 `WorkflowState`，graph node 无法收口
