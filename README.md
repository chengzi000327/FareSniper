# FareSniper

FareSniper 是一个面向自然语言机票搜索、低价发现和价格监控的全栈应用。用户可以输入“8 月 1 日北京到上海”一类需求，系统解析航线和日期，并把多个可用来源的状态与报价渐进更新到现有航班卡片。

## 当前能力

- 自然语言航班搜索：LangGraph 工作流解析出发地、目的地、未来日期、预算和偏好。
- 多来源渐进搜索：NDJSON 接口先返回来源状态，再增量返回报价，普通 JSON 搜索接口保持兼容。
- 国内航线：组合 FlyAI 的飞猪实时结果与独立 worker 每小时采集的携程快照。
- 国际航线：组合 FlyAI、SerpAPI Google Flights 销售平台/航司结果，以及匹配的携程快照。
- 价格监控：支持价格告警、推送订阅、价格历史和后台调度。
- 安全观测：LangSmith 记录搜索、provider 和携程 worker 的状态、数量、延迟等摘要，不记录密钥、raw offer、完整预订 URL 或第三方原始错误。
- Railway 部署：三个服务各用独立 Config-as-Code；backend pre-deploy 执行 migration，严格单副本 worker 负责每小时携程刷新。

## 能力边界

FareSniper 是搜索与比价工具，不在站内出票或支付。预订操作会跳转到第三方销售平台，价格与库存以对方页面为准。携程数据是最长 75 分钟有效的 worker 快照，不是每次请求现场抓取；缺少 provider key、来源超时或无库存时，对应来源会显示状态，其他来源仍可继续。

## 技术栈

- Frontend: Next.js App Router、React、TypeScript、Tailwind CSS、Vitest
- Backend: FastAPI、Pydantic v2、SQLAlchemy async、Alembic、Redis、APScheduler
- Agent: LangGraph、LangChain、OpenAI-compatible chat model providers
- Flight providers: FlyAI CLI、携程快照、SerpAPI Google Flights
- Observability: LangSmith 安全摘要 tracing、健康检查
- Infra: Railway、Docker、PostgreSQL、Redis、Python 3.13、Node.js 22、Chromium

## 目录结构

```text
backend/      FastAPI、Provider 聚合、数据库、worker 和观测能力
frontend/     Next.js 前端、PWA、渐进搜索和航班卡片
docs/         架构、计划和部署文档
scripts/      本地检查脚本
backend/railway.api.toml、backend/railway.worker.toml、frontend/railway.toml
```

## 本地开发

后端：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
uvicorn backend.main:app --reload
```

FlyAI provider 需要 Node.js 22、全局 `@fly-ai/flyai-cli@1.0.16` 和环境中的 `FLYAI_API_KEY`。生产运行时直接调用 `flyai`，不会在请求时通过 `npx` 下载 CLI，也不会写入 FlyAI 全局配置。

前端：

```bash
npm --prefix frontend install
npm --prefix frontend run dev
```

前端默认通过 `/api/*` 访问后端；分离部署时设置：

```dotenv
NEXT_PUBLIC_API_BASE_URL=https://<backend>.up.railway.app
```

## Provider 配置

完整变量见 [`backend/.env.example`](backend/.env.example)。关键生产设置：

```dotenv
ENABLE_MOCK_FALLBACK=false
FLYAI_API_KEY=
FLYAI_CLI_PATH=flyai
SERPAPI_API_KEY=
VARIFLIGHT_API_KEY=
FLIGHT_PROVIDER_TIMEOUT_SECONDS=10
CTRIP_SNAPSHOT_TTL_MINUTES=75
CTRIP_REFRESH_BATCH_SIZE=20
RUN_SCHEDULER_IN_API=false
```

真实 key 只写入本地未跟踪的 `backend/.env` 或 Railway Variables，不写入示例文件。

## LangSmith

```dotenv
LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=faresniper
LANGCHAIN_TRACING_V2=false
```

Tracing 必须同时有显式 `LANGSMITH_TRACING=true` 和 key 才启用。`LANGCHAIN_TRACING_V2` 始终保持 false；只有 Task 10 手工 wrapper 在局部 context 中启用自定义安全 span。

## Railway

Railway dashboard 中的三个服务都把 Root Directory 设为 `/`，Config File 分别设置为 `/backend/railway.api.toml`、`/backend/railway.worker.toml`、`/frontend/railway.toml`。backend 与 worker 生产构建共享 [`backend/Dockerfile`](backend/Dockerfile)；worker 必须严格单副本。

完整变量归属、Dockerfile/Nixpacks fallback、部署顺序、FlyAI 命令、NDJSON curl 和安全 smoke 语义见 [`docs/deployment/RAILWAY.md`](docs/deployment/RAILWAY.md)。

## 测试

```bash
pytest
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run build
```

默认测试不会调用付费 provider。只有环境中已经安全配置真实 key 时，才显式运行：

```bash
python -m backend.scripts.verify_flight_providers \
  --origin 北京 --destination 上海 --depart-date 2099-08-01
```

`2099-08-01` 仅为未来日期示例，过期后须替换为执行日之后的日期。

## 相关文档

- [Architecture](ARCHITECTURE.md)
- [PRD](PRD.md)
- [Railway Deployment](docs/deployment/RAILWAY.md)
