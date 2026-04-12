# FareSniper 项目计划（合并版）

## 一、现状快照

### 基础设施

| 服务 | 平台 | 状态 |
|------|------|------|
| PostgreSQL | Railway 内置 | 待 Step 10 在画布添加 |
| Redis | Railway 内置 | 待 Step 10 在画布添加 |
| 前端部署 | Railway | 待 Step 10 |
| 后端部署 | Railway | 待 Step 10 |

> 本地开发直接连 Railway 云端 PostgreSQL + Redis，不需要本地 Docker。Railway 会自动注入 `DATABASE_URL` 和 `REDIS_URL` 环境变量。

### 代码完成情况

| 层 | 文件 | 状态 |
|----|------|------|
| 前端 | 全部 4 个页面 + api-client + types/api.ts | ✅ 已完成 |
| 后端基础 | main.py + CORS + config.py | ✅ 已完成 |
| 工具层 | tools/{compare_prices, analyze_history, match_preference, generate_signals}.py | ✅ 已完成 |
| 数据源 | data_sources/{base, ctrip_source, registry}.py | ✅ 已完成（含 mock fallback）|
| LLM 客户端 | llm/client.py（heuristic 模式） | ✅ 已完成 |
| Schema 基础 | schemas/{common, search, memory}.py | ✅ 已完成（待 Step 5 对齐 DTO）|
| 旧记忆服务 | services/memory_service.py（JSON 文件） | ✅ 保留至 Step 8 |
| 旧搜索服务 | services/search_service.py | ✅ 保留至 Step 8 |
| utils | utils/airport_codes.py | ✅ 已完成 |
| 测试基础 | tests/conftest.py + test_airport_mapping.py + test_cors.py | ✅ 已完成 |
| 基础设施测试 | tests/test_infra.py（Railway PostgreSQL + Redis 连通） | ❌ 待 Step 1 补全 |

---

## 二、API 接口契约

### 通用约定

- Base URL 本地：`http://localhost:8000`，API 前缀：`/api`
- 所有字段使用 `snake_case`，前端在 `api-client` 层转 `camelCase`
- 金额：人民币整数；日期：`YYYY-MM-DD`；时间戳：ISO 8601 UTC
- 未接入登录前所有接口显式传 `user_id`，默认 `demo-user`

**错误响应格式：**
```json
{ "error": { "code": "INVALID_QUERY", "message": "destination is required", "details": {} } }
```

推荐错误码：`INVALID_QUERY` / `UNAUTHORIZED` / `NOT_FOUND` / `UPSTREAM_UNAVAILABLE` / `INTERNAL_ERROR`

---

### DealCardDto

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | `string` | 业务唯一 ID |
| `system_id` | `string` | 展示编号，如 `SYS.042` |
| `platform` | `string` | 数据来源，如 `ctrip` |
| `origin_city` | `string` | 出发城市中文名 |
| `origin_code` | `string` | 出发地三字码 |
| `destination_city` | `string` | 到达城市中文名 |
| `destination_code` | `string` | 到达地三字码 |
| `depart_date` | `string` | 出发日期 |
| `airline` | `string` | 航司名称 |
| `depart_time` | `string` | 起飞时间 `HH:mm` |
| `arrive_time` | `string` | 到达时间 `HH:mm` |
| `price` | `number` | 当前价格 |
| `original_price` | `number\|null` | 参考原价 |
| `discount_rate` | `number\|null` | 折扣百分比 |
| `cabin` | `string\|null` | 舱位 |
| `signals` | `string[]` | 值得买信号 |
| `confidence` | `'high'\|'medium'\|'low'` | 置信度 |
| `verdict` | `string` | 卡片级结论 |
| `booking_url` | `string\|null` | 购买链接 |

### 其他 DTO（简表）

**SearchQueryDto**：raw_text, normalized_text, origin_city, origin_code, destination_city, destination_code, date_start, date_end, budget

**SearchAnalysisDto**：min_price, max_price, avg_price, avg_90d, lower_than_avg, price_spread_pct, match_score, within_budget, matched_preferences[]

**SearchRecommendationDto**：action(`buy_now|watch|skip`), text, confidence, signals[]

**SearchResponseDto**：user_id, query, deals[], analysis, recommendation, meta

**MemoryItemDto**：id, field, label, value, value_display, source(`manual|auto`), updated_at

**MemoryResponseDto**：user_id, memories[], query_history[], click_history[], meta

**RecommendationCardDto**：id, title, reason, query_hint, tags[], preview_deal

**RecommendationsResponseDto**：user_id, cards[], meta

---

### 接口列表

| 方法 | 路径 | 用途 |
|------|------|------|
| GET | `/health` | 健康检查 |
| POST | `/api/search` | 自然语言搜索（对话页 + 探索页） |
| GET | `/api/memory?user_id=` | 记忆页首屏 |
| PATCH | `/api/memory` | 编辑/添加偏好 |
| DELETE | `/api/memory/{field}?user_id=` | 删除偏好 |
| GET | `/api/recommendations?user_id=` | 首页推荐卡 |

---

## 三、技术选型

| 层 | 选型 |
|---|------|
| Agent 框架 | AgentScope（`pip install agentscope`，Python 3.10+）|
| 数据库 | PostgreSQL 15（Railway 内置）— SQLAlchemy 2.0 async + Alembic |
| 缓存 | Redis 7（Railway 内置）— 短期记忆 + 偏好热缓存 |
| LLM | 统一 OpenAI 兼容接口，6 家 Provider |
| 部署 | Railway 全家桶（前端 + 后端 + PG + Redis）|

### LLM Provider 清单

| Provider | Base URL | 默认模型 |
|----------|----------|---------|
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| 通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus` |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash` |
| 豆包 | `https://ark.cn-beijing.volces.com/api/v3` | `doubao-pro-32k` |
| MiniMax | `https://api.minimax.io/v1` | `MiniMax-Text-01` |
| Kimi | `https://api.moonshot.cn/v1` | `moonshot-v1-8k` |

---

## 四、实施步骤

### Step 1：补全基础设施测试 🔄（当前步骤）

**缺失文件：`backend/tests/test_infra.py`**

```python
# 测试 Railway PostgreSQL：SELECT 1 返回成功
# 测试 Railway Redis：SET/GET 一个 key 返回成功
```

**conftest.py 需补充的 fixtures：**
```python
@pytest.fixture(scope="session")
async def db_engine():
    engine = create_async_engine(settings.database_url)
    yield engine
    await engine.dispose()

@pytest.fixture(scope="session")
async def redis_client():
    client = redis.from_url(settings.redis_url)
    yield client
    await client.aclose()
```

**验证：**
```bash
python -m pytest backend/tests/test_airport_mapping.py backend/tests/test_cors.py backend/tests/test_infra.py -v
```

---

### Step 2：数据库层 — SQLAlchemy models + Alembic

**先写测试** `backend/tests/test_db_models.py`（连接 Railway PostgreSQL）：
- 创建 UserPreference → 读取 → 验证字段完整
- 创建 QueryHistory → 验证 created_at 自动填充
- 创建 ClickHistory → 验证 JSONB 字段可存取
- 创建 ChatHistory → 验证消息读写
- 每个测试后 rollback

**新建 `backend/db/models.py`**（4 张表：preferences, query_history, click_history, chat_history）

**新建 `backend/db/session.py`**：
```python
engine = create_async_engine(settings.database_url, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
```

**Alembic 初始化**：
```bash
cd backend && alembic init db/migrations
alembic revision --autogenerate -m "initial tables"
alembic upgrade head
```

| 操作 | 文件 |
|------|------|
| 新建 | `backend/db/__init__.py`, `models.py`, `session.py`, `migrations/` |
| 修改 | `backend/config.py`（加 database_url, redis_url） |
| 修改 | `backend/requirements.txt`（加 sqlalchemy[asyncio], asyncpg, alembic） |

---

### Step 3：多 LLM Provider — 统一客户端

**先写测试** `backend/tests/test_llm_providers.py`：
- 构造每家 LLMProviderConfig → 验证 base_url/model 字段
- Mock httpx → chat_completion() 返回 str
- provider 不存在 → ValueError
- 主 provider 失败 → 自动 fallback

**新建 `backend/llm/providers.py`**（6 家 Provider 配置字典）

**重写 `backend/llm/client.py`**：
```python
@dataclass
class LLMProviderConfig:
    provider: str; api_key: str; base_url: str; model: str; timeout: float = 25.0

class UnifiedLLMClient:
    async def chat_completion(self, messages, provider=None, temperature=0.2) -> str: ...
    async def parse_intent(self, text) -> dict: ...
    async def generate_recommendation(self, flights, preferences, metrics) -> dict: ...
```

---

### Step 4：两层记忆系统

> ⚠️ 本步只新建 `backend/memory/`，**不删除** `backend/services/memory_service.py`（到 Step 8 再删）

**先写测试**：
- `test_memory_short_term.py`：Railway Redis 滑动窗口 10 条，TTL 验证
- `test_memory_long_term.py`：Railway PostgreSQL CRUD，preferences/history
- `test_memory_manager.py`：get_full_context 返回 {short_term, preferences, long_term_summary}

**新建目录**：`backend/memory/__init__.py`, `short_term.py`, `long_term.py`, `summarizer.py`, `manager.py`

关键常量：
```python
KEY_PREFIX = "faresniper:chat:"
WINDOW_SIZE = 10
TTL_SECONDS = 3600
SUMMARY_CACHE_TTL = 1800

FIELD_LABELS = {
    "price_anchor": "心理价位",
    "preferred_origins": "常用出发地",
    "preferred_destinations": "想去的地方",
    "frequent_destinations": "常去目的地",
    "travel_window": "出行时间偏好",
    "cabin_preference": "舱位偏好",
}
```

---

### Step 5：重写 Schemas 对齐前端 DTO

**先写测试** `backend/tests/test_schemas.py`：
- DealCardDto 含全部字段，model_validate 验证
- MemoryResponseDto 使用 `memories` 字段（非 `preferences`）
- SearchResponseDto 完整验证

**重写三个 schema 文件**（对齐 `frontend/types/api.ts`）：
- `backend/schemas/common.py`：ApiMeta, DealCardDto, RecommendationCardDto
- `backend/schemas/search.py`：SearchRequest, SearchQueryDto, SearchAnalysisDto, SearchRecommendationDto, SearchResponseDto
- `backend/schemas/memory.py`：MemoryItemDto, MemoryResponseDto, MemoryPatchRequest, RecommendationsResponseDto

---

### Step 6：AgentScope Spike + Plan-and-Execute

**6.0 必做 Spike（先验证再实现）：**
```bash
pip install agentscope
python -c "
from agentscope.agents import AgentBase
import inspect
print('reply is coroutine:', inspect.iscoroutinefunction(AgentBase.reply))
"
```
- 若 True → 直接 `await skill.reply(msg)`
- 若 False → 用 `asyncio.to_thread(skill.reply, msg)` 包装

**先写测试**：`test_intention_agent.py`, `test_orchestration_agent.py`, `test_skill_registry.py`

**新建目录结构**：
```
backend/agents/__init__.py, base.py, intention_agent.py, orchestration_agent.py
backend/skills/_registry.py (LazyAgentRegistry)
backend/skills/{flight_search,preference_match,decision_maker,memory_query}/SKILL.md + agent.py
```

---

### Step 7：flights_monitor 集成

**7.0 必做 Spike：**
```bash
git clone https://github.com/liuzhunai/flights_monitor /tmp/fm_check
grep -r "^def \|^async def \|^class " /tmp/fm_check --include="*.py" | head -30
```

**用户操作**：将 flights_monitor fork 到 `backend/third_party/flights_monitor/`

**先写测试** `backend/tests/test_ctrip_source.py`：
- normalize() 补全 system_id, origin_city, destination_city, confidence, verdict
- 第三方 import 失败 → 返回 `[]`

**修改 `backend/data_sources/ctrip_source.py`**：用 spike 结果适配真实接口

---

### Step 8：API 路由层重构

> ⚠️ 本步完成后删除：`backend/services/memory_service.py` 和 `backend/services/search_service.py`

**先写测试**：`test_search_api.py`, `test_memory_api.py`, `test_recommendations_api.py`

**重写 `backend/main.py`**（使用 lifespan，不用已废弃的 on_event）：
```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title=settings.app_name, lifespan=lifespan)
```

注入顺序：基础设施（engine, redis）→ 记忆系统 → 数据源 → Skill/Agent → 路由

**重写**：`backend/api/search.py`, `backend/api/memory.py`（补 DELETE 路由）, `backend/api/recommendations.py`

---

### Step 9：容错机制

**先写测试** `backend/tests/test_resilience.py`：
- CircuitBreaker：5 次失败 → OPEN → 等待 → HALF_OPEN → CLOSED
- retry_with_backoff：3 次重试，指数退避

**新建 `backend/resilience/circuit_breaker.py`** + **`backend/resilience/retry.py`**

修改 `llm/client.py`（CircuitBreaker 包装每个 provider）和 `ctrip_source.py`（retry_with_backoff 包装抓取）

---

### Step 10：云端部署

**先写端到端测试** `backend/tests/test_e2e.py`（ENABLE_MOCK_FALLBACK=true）：
- 完整流程：POST /search → GET /memory → PATCH /memory → DELETE /memory/{field} → GET /recommendations
- 每步用 Pydantic DTO model_validate

**新建 `backend/nixpacks.toml`**（让 Railway Nixpacks 安装 Chromium，无需 Dockerfile）：
```toml
[phases.setup]
nixPkgs = ["chromium", "chromedriver"]
```

**部署步骤：**

Railway 画布操作：
1. railway.app → 新建 Project → 连接 GitHub repo
2. 画布上 Add Service → Database → **PostgreSQL**（自动生成 `DATABASE_URL`）
3. 画布上 Add Service → Database → **Redis**（自动生成 `REDIS_URL`）
4. 画布上 Add Service → GitHub Repo → 选 `backend/` 目录（自动检测 nixpacks.toml）
5. 将 PostgreSQL 和 Redis 的变量关联到后端 Service（画布连线）
6. 填写其他环境变量（LLM keys、APP_NAME 等）

前端（Railway）：
1. 画布上 Add Service → GitHub Repo → 选 `frontend/` 目录（自动识别 Next.js）
2. 将后端 Service 的域名注入：`NEXT_PUBLIC_API_URL` = Railway backend 域名
3. push 即自动构建部署

**更新 `backend/.env.example`**：
```bash
# DATABASE_URL 和 REDIS_URL 由 Railway 画布关联后自动注入
# 本地开发：从 Railway 控制台 PostgreSQL/Redis Service 的 Connect 面板复制
DATABASE_URL=postgresql+asyncpg://postgres:[PASSWORD]@[HOST].railway.internal:5432/railway
REDIS_URL=redis://default:[PASSWORD]@[HOST].railway.internal:6379
APP_NAME=FareSniper Backend
API_PREFIX=/api
DEFAULT_USER_ID=demo-user
ENABLE_MOCK_FALLBACK=true
LLM_DEFAULT_PROVIDER=deepseek
LLM_FALLBACK_PROVIDER=qwen
DEEPSEEK_API_KEY=
QWEN_API_KEY=
GLM_API_KEY=
DOUBAO_API_KEY=
MINIMAX_API_KEY=
KIMI_API_KEY=
```

---

## 五、文件变更总览

### 新建（~40 个文件）
```
backend/db/__init__.py, models.py, session.py, migrations/
backend/llm/providers.py
backend/memory/__init__.py, short_term.py, long_term.py, summarizer.py, manager.py
backend/agents/__init__.py, base.py, intention_agent.py, orchestration_agent.py
backend/skills/_registry.py
backend/skills/{flight_search,preference_match,decision_maker,memory_query}/SKILL.md + agent.py
backend/resilience/__init__.py, circuit_breaker.py, retry.py
backend/third_party/__init__.py
backend/nixpacks.toml
backend/tests/ ~19 个测试文件
```

### 重写（~10 个文件）
```
backend/schemas/common.py, search.py, memory.py
backend/llm/client.py
backend/api/search.py, memory.py, recommendations.py
backend/main.py
backend/data_sources/ctrip_source.py
backend/config.py
backend/requirements.txt
backend/.env.example
```

### Step 8 完成后删除（2 个）
```
backend/services/memory_service.py → 功能迁移到 backend/memory/
backend/services/search_service.py → 被 Agent pipeline 替代
```

### 始终保留不动
```
backend/tools/*.py           — 4 个纯函数工具
backend/data_sources/base.py — DataSource 抽象基类
backend/data_sources/registry.py
backend/services/recommendation_service.py — Step 8 前过渡用
frontend/**                  — 前端代码完全不动
```

---

## 六、最终验证清单

```bash
cd /Users/chengzi/Documents/FareSniper
python -m pytest backend/tests/ -v
# 预期全部通过

# 本地联调（直连 Railway 云端 PG+Redis，无需本地 Docker）
cd backend && uvicorn backend.main:app --reload
cd frontend && npm run dev
# 或 push GitHub → Railway 全家桶自动部署
```

