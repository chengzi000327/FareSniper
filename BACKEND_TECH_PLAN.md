# 特价机票发现平台 - 后端技术方案

## 1. 目标与职责

后端是整个项目的业务核心，负责承载真实查询、意图解析、偏好记忆、推荐生成和架构演进。

你的后端职责不是简单提供 CRUD，而是把以下能力收拢到 Python 侧：
- 自然语言搜索入口
- 航班数据抓取与标准化
- 用户偏好存储与读取
- LLM 意图解析与推荐生成
- 阶段三的 Agent 化调度与记忆系统

项目的关键边界是：
- 前端只负责展示
- 后端负责全部业务判断
- Tool 负责执行
- Agent 负责理解、调度、总结

## 2. 分阶段后端路线

### 阶段二：最小真实后端

目标：尽快打通“真实数据 + 真实 AI + 可部署”闭环。

实现原则：
- 先不用 AgentScope
- 先不用 PostgreSQL/Redis
- 先不用复杂并行
- 用 FastAPI + flights_monitor + LLM + JSON 文件先跑通

这阶段的判断标准不是架构优雅，而是能否尽快稳定返回真实结果。

### 阶段三：终态架构重构

目标：把阶段二的可运行代码升级为可维护、可扩展、可交付的系统。

重构方向：
- JSON 文件升级为 PostgreSQL + Redis
- Python 函数链升级为 Plan-and-Execute
- 单体调用升级为 Agent + Skill + Tool 分层
- 同步体验升级为 SSE + 容错 + 并行

## 3. 技术选型

- Web 框架：FastAPI
- 运行语言：Python 3.11+
- Agent 框架：AgentScope
- ORM：SQLAlchemy 2.0 async
- 数据库：PostgreSQL 15
- 缓存：Redis 7
- 数据源：`flights_monitor`
- LLM 接入：先单供应商，后多供应商抽象
- 部署：本地 `docker-compose`，线上 Railway/Render/自有服务器

阶段二推荐最小依赖：
- `fastapi`
- `uvicorn`
- `httpx`
- `pydantic`
- `python-dotenv`

阶段三再补：
- `sqlalchemy`
- `asyncpg`
- `alembic`
- `redis`
- `agentscope`

## 4. 推荐目录结构

```txt
backend/
├── main.py
├── api/
│   ├── search.py
│   ├── memory.py
│   ├── recommendations.py
│   └── chat.py
├── services/
│   ├── search_service.py
│   ├── recommendation_service.py
│   └── memory_service.py
├── data_sources/
│   ├── base.py
│   ├── ctrip_source.py
│   └── registry.py
├── tools/
│   ├── fetch_flights.py
│   ├── compare_prices.py
│   ├── analyze_history.py
│   ├── match_preference.py
│   └── generate_signals.py
├── memory/
│   ├── short_term.py
│   ├── long_term.py
│   ├── summarizer.py
│   └── manager.py
├── llm/
│   ├── client.py
│   ├── config.py
│   └── providers/
├── agents/
│   ├── base.py
│   ├── intention_agent.py
│   └── orchestration_agent.py
├── skills/
│   ├── flight_search/
│   ├── preference_match/
│   ├── decision_maker/
│   ├── memory_query/
│   └── _registry.py
├── db/
│   ├── models.py
│   ├── session.py
│   └── migrations/
├── resilience/
│   ├── circuit_breaker.py
│   └── retry.py
├── third_party/
│   └── flights_monitor/
├── schemas/
│   ├── search.py
│   ├── memory.py
│   └── common.py
├── config.py
└── memory.json
```

说明：
- 阶段二可以先没有 `agents/`、`skills/`、`db/`，但目录设计最好提前留好
- 路由层只负责协议，不写业务
- 业务集中在 `services/`
- 和 flights_monitor 的耦合必须收在 `data_sources/`

## 5. 阶段二最小闭环设计

### 5.1 请求主流程

建议把阶段二的后端流程固定为下面这条函数链：

1. 接收搜索请求
2. `parse_intent(text)` 解析用户需求
3. 从 `memory.json` 读取用户偏好
4. 调 `ctrip_source.search_flights()` 获取真实航班
5. 用纯 Python 计算匹配度和信号
6. 调 `generate_recommendation()` 输出推荐文案
7. 返回结构化结果给前端

这样做的好处是：
- 足够简单
- 以后可平滑映射到 IntentionAgent + OrchestrationAgent
- 每个阶段函数都能单测

### 5.2 核心 API

建议最先完成 3 个接口：

#### `POST /api/search`

请求：
```json
{
  "user_id": "u1",
  "message": "五一去三亚，600以内"
}
```

响应：
```json
{
  "query": {
    "origin": "BJS",
    "destination": "SYX",
    "date_start": "2026-05-01",
    "date_end": "2026-05-03",
    "budget": 600
  },
  "flights": [],
  "comparison": {
    "min_price": 389,
    "max_price": 420,
    "avg_90d": 540,
    "lower_than_avg": 0.28
  },
  "preference": {
    "match_score": 0.85,
    "within_budget": true
  },
  "recommendation": {
    "recommendation": "建议现在买",
    "signals": ["近90天低位", "符合心理价位"],
    "confidence": "high"
  }
}
```

#### `GET /api/memory`

用途：
- 查询用户偏好
- 给个人中心展示

#### `PATCH /api/memory`

用途：
- 更新心理价位
- 更新常去目的地
- 标记来源 `manual` 或 `auto`

#### `GET /api/recommendations`

用途：
- 首页展示热门推荐
- 后期可加入基于偏好的个性化推荐

## 6. 数据源封装方案

### 6.1 封装目标

`flights_monitor` 是能力来源，但不能直接在业务层到处调用。

必须通过 `data_sources/ctrip_source.py` 做一层标准化封装，解决：
- 同步 Selenium 接口与异步 FastAPI 的衔接
- 返回结果格式统一
- 后续多平台扩展
- 异常统一处理

### 6.2 标准接口

建议抽象：

```python
class DataSource(ABC):
    name: str

    async def search_flights(
        self,
        origin: str,
        destination: str,
        date_start: str,
        date_end: str,
    ) -> list[dict]:
        ...

    async def get_history_prices(self, route: str, days: int) -> list[dict]:
        ...
```

### 6.3 `ctrip_source.py` 的职责

- 调 flights_monitor
- 用线程池包装同步 Selenium 调用
- 把结果转换成统一结构
- 屏蔽第三方字段命名差异

统一返回建议至少包含：
- 平台
- 航司
- 起点/终点
- 出发日期
- 起飞/到达时间
- 价格
- 舱位信息

### 6.4 风险控制

Selenium 是当前最大不稳定因素，需要从阶段二就留好兜底：
- 加超时
- 加异常捕获
- 查不到数据时返回标准空结果而不是抛裸异常
- 后期增加缓存和熔断

## 7. LLM 分层设计

阶段二只做两件事：
- `parse_intent(text)`
- `generate_recommendation(flights, preferences, metrics)`

建议不要把 LLM 直接散落在业务函数里，而是收敛为 `llm/client.py` 或 `llm.py`。

### 7.1 `parse_intent`

职责：
- 从自然语言里解析地点、时间、预算、偏好倾向
- 输出结构化查询参数

输出建议固定格式：
```json
{
  "origin": "BJS",
  "destination": "SYX",
  "date_start": "2026-05-01",
  "date_end": "2026-05-03",
  "budget": 600
}
```

要求：
- 尽量 JSON 化
- 解析失败时给出默认兜底
- 时间表达尽量转绝对日期

### 7.2 `generate_recommendation`

职责：
- 接收已经计算好的数字结果
- 输出一句推荐文案和信号标签

约束：
- 不允许模型自己算百分比
- 不允许模型决定原始排序逻辑
- 模型只负责“翻译”和“总结”

## 8. 业务分层建议

建议从一开始就按这四层拆，即使阶段二先写得简化一些。

### 8.1 API 层

职责：
- 校验请求
- 调 service
- 返回统一响应

不做：
- 不直接调 flights_monitor
- 不直接写 JSON 文件

### 8.2 Service 层

职责：
- 编排一次完整业务流程
- 串联 memory、llm、data source、tools

这是阶段二最重要的层，后续重构成 Agent 也主要是拆解这层。

### 8.3 Tool 层

职责：
- 纯计算
- 无副作用或副作用可控
- 不依赖 LLM

典型函数：
- 价格比较
- 历史均价计算
- 偏好匹配度打分
- 值得买信号生成

### 8.4 DataSource 层

职责：
- 适配外部平台
- 屏蔽第三方实现细节

## 9. 记忆系统设计

### 9.1 阶段二：`memory.json`

目标是快速可用，而不是完美。

建议 JSON 结构：
```json
{
  "u1": {
    "preferences": {
      "price_anchor": 600,
      "frequent_destinations": ["SYX", "KMG"]
    },
    "query_history": [],
    "click_history": []
  }
}
```

注意点：
- 读写要加文件锁或最少做串行写入，避免并发覆盖
- 对外接口保持与未来数据库字段一致
- JSON 文件只是临时存储层，不要把它和业务逻辑绑死

### 9.2 阶段三：两层记忆

短期记忆：
- Redis List
- 最近 10 轮对话
- TTL 1 小时

长期记忆：
- PostgreSQL
- 存偏好、查询历史、点击历史、聊天历史

异步摘要：
- 从聊天历史生成 200 字长期偏好摘要
- 缓存到 Redis
- 供 IntentionAgent 作为 system context 使用

### 9.3 MemoryManager

建议阶段三把所有记忆访问统一收敛到 `MemoryManager`：
- 读取上下文
- 写入消息
- 更新偏好
- 写查询历史
- 触发摘要刷新

这样 Agent 和 Service 都只依赖一个入口。

## 10. 阶段三 Agent 化改造方案

### 10.1 IntentionAgent

职责：
- 理解用户意图
- 读取短期/长期记忆上下文
- 输出结构化计划 `agent_schedule`

输入：
- 用户原始文本
- 短期对话
- 长期摘要
- 可用 skill 元数据

输出：
- `rewritten_query`
- `key_entities`
- `agent_schedule`

### 10.2 OrchestrationAgent

职责：
- 根据 priority 调度技能
- 同优先级并行，跨优先级串行
- 聚合结果并触发异步写记忆

这是系统执行总控，不负责做具体价格计算。

### 10.3 Skills

建议至少拆出 4 个：
- `flight_search`
- `preference_match`
- `memory_query`
- `decision_maker`

原则：
- Skill 是相对独立的能力单元
- 每个 Skill 都有 `SKILL.md` 和 `script/agent.py`
- Skill 可被注册表发现并按需懒加载

## 11. Tool 设计原则

Tool 必须满足：
- 纯代码
- 输入输出稳定
- 可单测
- 不依赖大模型

建议优先做的 Tool：
- `fetch_flights`
- `compare_prices`
- `analyze_history`
- `match_preference`
- `generate_signals`

其中最重要的是把“计算”和“文案”彻底拆开，这样后续模型不稳定时也不影响核心判断结果。

## 12. 数据库设计建议

阶段三建议至少有四张主表：
- `preferences`
- `query_history`
- `click_history`
- `chat_history`

### `preferences`

用途：
- 存用户长期偏好
- 支持手动和自动来源

关键字段：
- `user_id`
- `field`
- `value(JSONB)`
- `source`
- `updated_at`

### `query_history`

用途：
- 记录用户搜过什么
- 支持后续个性化推荐和总结

### `click_history`

用途：
- 记录用户点过哪些票
- 作为未来偏好归因依据

### `chat_history`

用途：
- 提供长期摘要原始材料

## 13. 容错与稳定性

从阶段二开始就建议预留这些稳定性策略。

### 13.1 超时

- Selenium 查询必须有超时
- LLM 调用必须有超时

### 13.2 重试

可重试场景：
- 网络抖动
- LLM 短暂失败
- 第三方抓取临时异常

不可盲目重试：
- 参数错误
- 解析逻辑错误

### 13.3 熔断

阶段三建议对两类调用加熔断：
- LLM provider
- Selenium 数据源

### 13.4 降级

建议降级路径：
- 抓取失败时只返回“暂无结果”与友好提示
- 推荐生成失败时仍返回结构化航班数据
- 历史分析失败时隐藏相应信号，而不是整个请求失败

## 14. SSE 方案

阶段三建议新增 `POST /api/chat` 作为流式入口。

后端职责：
- 先发状态事件
- 再逐步推送推荐文案或执行进度
- 最后返回结构化结果

建议事件顺序：
1. `status: parsing_intent`
2. `status: searching_flights`
3. `status: generating_recommendation`
4. `final_result`

这样前端能非常直观地显示“系统正在做什么”。

## 15. 测试建议

至少覆盖三层测试：

### 单元测试

覆盖：
- `match_preference`
- `compare_prices`
- `analyze_history`
- memory 读写

### 集成测试

覆盖：
- `/api/search`
- `/api/memory`
- `/api/recommendations`

### 冒烟测试

覆盖真实链路：
- 输入一句查询
- 返回真实携程数据
- 返回推荐文案

对 `flights_monitor` 建议加 mock 适配层，避免测试强依赖真实 Selenium。

## 16. 开发顺序建议

1. 先把 FastAPI 路由和 Pydantic schema 搭起来。
2. 再把 `memory.json` 读写做出来。
3. 再封装 `ctrip_source.py`，单独跑通真实抓取。
4. 再补 `parse_intent()` 和 `generate_recommendation()`。
5. 再串起 `search_service` 完成闭环。
6. 本地联调前端。
7. 阶段二稳定后，再开始数据库和 Agent 化重构。

## 17. 与前端的协作契约

后端需要给前端稳定承诺：
- 响应字段名尽早冻结
- 错误格式统一
- 空结果与失败结果分开表达
- 推荐文案与结构化指标同时返回
- 阶段三的 SSE 事件格式提前约定

后端不应该要求前端：
- 自己解析意图
- 自己推导预算
- 自己排序结果
- 自己拼接推荐逻辑

## 18. 当前最推荐的落地方式

如果以“你负责后端、另一位同学负责前端”为前提，最稳妥的做法是：

1. 后端先按阶段二做最小闭环，不等待 AgentScope。
2. 接口形状尽量贴近阶段三终态，避免未来返工。
3. 把 flights_monitor 的所有不稳定性包进 `data_sources/`。
4. 把 LLM 的职责严格限制在“解析”和“总结”。
5. 等前后端联调稳定后，再做阶段三的数据库与 Agent 化重构。

## 19. 最终交付标准

后端方案完成后，应该满足以下标准：
- 阶段二能真实返回携程数据和推荐结果
- 前端可以只依赖稳定 API 开发
- 阶段三可以在不推翻业务边界的情况下升级为 Agent 架构
- 数据源、记忆、LLM、工具计算彼此解耦，可长期演进
