# Railway 部署

FareSniper 在 Railway 中使用 `backend`、`worker`、`frontend` 三个服务。携程浏览器不在 Railway 运行，而是在独立 Mac collector 上运行。

## Dashboard 设置

| 服务 | Root Directory | Config File | 副本 |
| --- | --- | --- | --- |
| `backend` | `/` | `/backend/railway.api.toml` | 1 或按 API 流量扩展 |
| `worker` | `/` | `/backend/railway.worker.toml` | **严格单副本** |
| `frontend` | `/frontend` | `/frontend/railway.toml` | 1 或按流量扩展 |

worker 必须严格单副本，以免提醒扫描和定时需求播种重复执行。三个 Config-as-Code 文件各自只描述一个 deployment。

## 构建与启动

backend 和 worker 的生产构建共享 `backend/Dockerfile`。镜像包含 Python 3.13、Node.js 22、固定 `@fly-ai/flyai-cli@1.0.16` 和 `backend/requirements.txt`，不包含 Chromium、ChromeDriver、Selenium collector 或用户 profile。

- API：pre-deploy 运行 `alembic -c backend/alembic.ini upgrade head`，Docker CMD 启动 Uvicorn，healthcheck 为 `/health`。
- worker：启动 `python -m backend.workers.run_all`，只负责调度、需求队列和提醒，不导入 `backend.collector` 或浏览器模块。
- frontend：在 `/frontend` 执行 `npm ci && npm run build`，再以 `npm run start -- -p $PORT` 启动。

`backend/nixpacks.toml` 是 API 的人工 fallback：

```bash
nixpacks build . --config backend/nixpacks.toml
```

它同样不安装浏览器，只保留 Python、Node 和固定 FlyAI CLI。Railway 构建和请求路径都不执行 `npx` 或 `flyai config set`。

## Backend Variables

```dotenv
DATABASE_URL=
REDIS_URL=
JWT_SECRET=
CORS_ORIGINS=[]

MODEL_BASE_URL=
MODEL_API_KEY=
MODEL_INTENT=
MODEL_JUDGE=
MODEL_AGENT=
MODEL_THINKING=disabled

ENABLE_MOCK_FALLBACK=false
FLYAI_API_KEY=
FLYAI_CLI_PATH=flyai
SERPAPI_API_KEY=
FLIGHT_PROVIDER_TIMEOUT_SECONDS=10

CTRIP_COLLECTOR_TOKEN=
CTRIP_SNAPSHOT_TTL_MINUTES=75
CTRIP_COLLECTOR_HEARTBEAT_TIMEOUT_SECONDS=180
CTRIP_COLLECTOR_LEASE_SECONDS=180
RUN_SCHEDULER_IN_API=false

FARESNIPER_LANGSMITH_TRACING=true
LANGSMITH_TRACING=false
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=faresniper
LANGCHAIN_TRACING_V2=false
```

`SERPAPI_API_KEY` 可选；缺少时只禁用 Google Flights 来源。`FLYAI_API_KEY` 和 `CTRIP_COLLECTOR_TOKEN` 在启用相应来源时必填。`CTRIP_COLLECTOR_TOKEN` 使用高熵 token68 值，并与 Mac `collector.env` 保持一致。

## Worker Variables

```dotenv
DATABASE_URL=
REDIS_URL=
RUN_SCHEDULER_IN_API=false
VARIFLIGHT_API_KEY=

FARESNIPER_LANGSMITH_TRACING=true
LANGSMITH_TRACING=false
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=faresniper
LANGCHAIN_TRACING_V2=false
```

worker 不需要模型变量，也不得配置 FlyAI、SerpAPI、携程 token、浏览器路径、profile 或 Cookie。`VARIFLIGHT_API_KEY` 仅用于可选的旧 `hourly_scrape` 调度；未配置时该任务不注册。携程每小时任务只播种待采集航线，真正的页面采集由 Mac 完成。

## Frontend Variables

```dotenv
NEXT_PUBLIC_API_BASE_URL=https://<backend>.up.railway.app
```

同时把 frontend 域名加入 backend 的 `CORS_ORIGINS`。

## LangSmith

`FARESNIPER_LANGSMITH_TRACING=true` 启用项目的手工安全 span。不要开启 `LANGSMITH_TRACING`，不要开启 `LANGCHAIN_TRACING_V2`。自动 instrumentation 可能记录未经 allowlist 处理的用户输入或第三方数据。

允许的 span 只包含航线、日期、状态、结果数量、延迟、缓存年龄和匿名 job id。禁止记录密钥、Cookie、完整消息、raw offer、完整预订 URL 和第三方原始错误。

相关 trace 名称包括 `flight_search`、`ctrip_collector_claim`、`ctrip_local_collect` 和 `ctrip_collector_ingest`。

## 部署顺序

1. 创建独立 PostgreSQL 和 Redis，并给 backend/worker 配置各自变量。
2. 部署 backend，确认 pre-deploy migration 成功。
3. 串行检查数据库已经在 Alembic head：

```bash
alembic -c backend/alembic.ini current --check-heads
```

不要在共享 `TEST_DATABASE_URL` 上并行运行 downgrade/upgrade 与业务测试；migration 测试会短暂改变 schema。

4. 部署严格单副本 worker，确认 scheduler 启动。
5. 部署 frontend，并更新 backend `CORS_ORIGINS`。
6. 按 [`MAC_CTRIP_COLLECTOR.md`](MAC_CTRIP_COLLECTOR.md) 配置 Mac collector，完成可见登录后再激活 launchd。

## 验证

先检查服务：

```bash
curl -fsS https://<backend>.up.railway.app/health
```

真实票价验证需要环境中已有 `FARESNIPER_API_URL`、`FARESNIPER_VERIFY_JWT` 和 `CTRIP_COLLECTOR_TOKEN`。所有值都不得写入命令历史或仓库文件。使用未来日期：

```bash
python -m backend.scripts.verify_live_fares \
  --origin 北京 \
  --destination 三亚 \
  --depart-date 2099-08-01 \
  --timeout-seconds 180 \
  --require-fresh
```

脚本依次检查 Mac heartbeat、航线 job 状态、携程数字价格和 HTTPS 预订链接，并确认 `analysis.min_price`、卡片价格与推荐文本一致。stdout 只输出 `collector`、`job`、币种/价格和固定 trace 名称，不输出 token、JWT、URL 或 raw payload。

## 能力边界

- FlyAI/飞猪是实时来源；SerpAPI 是可选国际来源。
- 携程是由 Mac 采集并上传的快照，默认有效期 75 分钟；`--require-fresh` 会拒绝只有过期快照的结果。
- 单个来源 disabled、empty、timeout 或 error 不阻止其他来源返回。
- FareSniper 只提供比价和第三方跳转，不保证最终库存或成交价。
