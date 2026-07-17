# Railway 部署

FareSniper 在 Railway dashboard 中创建三个独立服务：`backend`、`worker`、`frontend`。每个 Config-as-Code 文件只描述一个 deployment。

## Dashboard 设置

三个服务都共享完整 monorepo，Root Directory 一律设为 `/`。Config File 使用仓库绝对路径：

| 服务 | Root Directory | Config File | 副本 |
| --- | --- | --- | --- |
| `backend` | `/` | `/backend/railway.api.toml` | 1 或按 API 流量扩展 |
| `worker` | `/` | `/backend/railway.worker.toml` | **严格单副本** |
| `frontend` | `/` | `/frontend/railway.toml` | 1 或按前端流量扩展 |

worker 必须严格单副本。携程每小时任务本身有数据库 advisory lock，但同一进程中的告警扫描和旧 `hourly_scrape` 没有全局跨副本锁；增加 worker 副本会重复执行这些任务。

## 构建与启动

backend 与 worker 的生产构建都使用 `backend/Dockerfile`。该镜像从仓库根构建，包含 Python 3.13、Debian Chromium/ChromeDriver、Node.js 22、固定 `@fly-ai/flyai-cli@1.0.16`，并安装：

```text
backend/requirements.txt
backend/third_party/flights_monitor/requirements.txt
```

容器 `WORKDIR` 是仓库根 `/app`，因此 `python -m backend...` 可以正常导入。`backend/nixpacks.toml` 仅是明确的人工 fallback，不是生产 Railway builder；它同样使用 repo-root requirements 路径并固定 Node/FlyAI CLI。

服务生命周期由各自 config 管理：

- API：`preDeployCommand` 单独运行 `alembic -c backend/alembic.ini upgrade head`；start 只运行 Uvicorn；healthcheck 是 `/health`。
- worker：start 保持 `python -m backend.workers.run_all`，不重复 migration。
- frontend：从 repo root 显式执行 `npm --prefix frontend ci`、build 和 start。

FlyAI 运行时直接调用 `flyai` 并从环境读取 `FLYAI_API_KEY`。构建和请求路径不执行 `npx`，也不执行 `flyai config set`。

`npx skills add alibaba-flyai/flyai-skill` 安装的是 coding-agent host 的开发说明，不是 FareSniper 生产依赖。Railway 不安装该 skill。

## Backend Variables

```dotenv
DATABASE_URL=<Railway PostgreSQL reference>
REDIS_URL=<Railway Redis reference>
MODEL_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MODEL_API_KEY=
MODEL_INTENT=qwen-plus
MODEL_JUDGE=deepseek-v3
MODEL_AGENT=qwen-plus
MODEL_THINKING=disabled
JWT_SECRET=
CORS_ORIGINS=["https://<frontend>.up.railway.app"]

ENABLE_MOCK_FALLBACK=false
FLYAI_API_KEY=
FLYAI_CLI_PATH=flyai
SERPAPI_API_KEY=
FLIGHT_PROVIDER_TIMEOUT_SECONDS=10
CTRIP_SNAPSHOT_TTL_MINUTES=75
RUN_SCHEDULER_IN_API=false

LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=faresniper
LANGCHAIN_TRACING_V2=false
```

Provider key 示例故意留空，实际值只写 Railway Variables。缺少 FlyAI 或 SerpAPI key 只禁用对应来源，不阻止 API 启动。生产必须保持 `ENABLE_MOCK_FALLBACK=false`。

## Worker Variables

```dotenv
DATABASE_URL=<same Railway PostgreSQL reference>
REDIS_URL=<same Railway Redis reference>
CTRIP_SNAPSHOT_TTL_MINUTES=75
CTRIP_REFRESH_BATCH_SIZE=20
CTRIP_REQUEST_DELAY_MIN_SECONDS=2
CTRIP_REQUEST_DELAY_MAX_SECONDS=5
VARIFLIGHT_API_KEY=
RUN_SCHEDULER_IN_API=false

LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=faresniper
LANGCHAIN_TRACING_V2=false
```

携程 `ctrip_hourly_refresh` 无论 VariFlight 是否配置都在每小时整点运行。只有配置 `VARIFLIGHT_API_KEY` 时，scheduler 才注册旧 `hourly_scrape`；未配置时不会固定产生失败任务。如启用告警推送，还需给 worker 配置 VAPID/通知变量。

## Frontend Variables

```dotenv
NEXT_PUBLIC_API_BASE_URL=https://<backend>.up.railway.app
```

同时把 frontend 域名加入 backend 的 `CORS_ORIGINS`。

## Custom-only LangSmith

`LANGSMITH_TRACING=true` 只启用 Task 10 的手工安全 span。应用进程始终把 `LANGCHAIN_TRACING_V2` 保持为 `false`，同时把 LangSmith key/project/endpoint 提供给局部 `tracing_context(enabled=True)`。不要开启 `LANGCHAIN_TRACING_V2`，否则第三方自动 instrumentation 可能记录未经 allowlist 处理的输入。

自定义 span 只记录航线/日期、状态、数量、延迟与缓存年龄等摘要，不记录密钥、完整用户消息、raw offer、预订 URL 或第三方原始错误。`/health` 的 `langsmith_ok` 使用同一个 custom-tracing 安全启用条件。

## 部署顺序

1. 创建 PostgreSQL/Redis，并配置 backend 与 worker Variables。
2. 按 dashboard 表配置并部署 backend；确认 pre-deploy migration 和 `/health`。
3. 部署严格单副本 worker；确认 `ctrip_hourly_refresh` 每小时运行。
4. 部署 frontend，并更新 backend `CORS_ORIGINS`。

## 验证

`2099-08-01` 只是未来日期示例。该日期失效后，必须替换成执行当天之后的日期；城市参数使用中文全称。

```bash
flyai --help
flyai search-flight --origin "北京" --destination "上海" --dep-date 2099-08-01 --sort-type 3
```

渐进 NDJSON：

```bash
curl -N -X POST "https://<backend>/api/search/stream" \
  -H "Authorization: Bearer <session-token>" \
  -H "Content-Type: application/json" \
  -d '{"session_id":null,"message":"8月1日北京到上海"}'
```

只有目标环境已安全配置 provider key 时才运行真实 smoke：

```bash
python -m backend.scripts.verify_flight_providers \
  --origin 北京 --destination 上海 --depart-date 2099-08-01
python -m backend.scripts.verify_flight_providers \
  --origin 上海 --destination 新加坡 --depart-date 2099-08-01
```

stdout 永远只有 `provider_statuses`、`deal_count`、`sellers`。至少一个 provider 为 `success` 或 `empty` 时退出 0；只有 error/timeout/disabled/queued/stale 或没有 provider 时退出 1；输入不合法时退出 2。输出不包含 key、URL、raw offer、raw error 或疑似敏感 seller。

## 能力边界

- 国内航线使用 FlyAI 实时结果与携程小时快照；国际航线使用 FlyAI、SerpAPI 和匹配的携程快照。
- 单个来源 disabled、超时或失败不会阻止其他来源完成。
- FareSniper 只展示报价和第三方跳转，不在站内出票、支付或保证库存。
- 携程是最长 75 分钟有效的 worker 快照，不是每次请求现场抓取。
