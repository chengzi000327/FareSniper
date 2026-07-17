# Railway 部署

FareSniper 在 Railway 上使用 `backend`、`worker`、`frontend` 三个服务，并连接同一个 PostgreSQL。密钥只写入对应服务的 Railway Variables，不写入仓库、构建命令、日志或 smoke 输出。

## 服务职责

| 服务 | 启动命令 | 职责 |
| --- | --- | --- |
| `backend` | `alembic -c backend/alembic.ini upgrade head && uvicorn backend.main:app --host 0.0.0.0 --port $PORT` | 先迁移数据库，再提供 JSON/NDJSON 搜索 API |
| `worker` | `python -m backend.workers.run_all` | 每小时刷新携程快照，并运行现有后台调度任务 |
| `frontend` | `npm --prefix frontend run start -- -p $PORT` | 提供 Next.js 前端 |

API 服务必须设置 `RUN_SCHEDULER_IN_API=false`。携程采集由独立 `worker` 独占：每小时整点领取一批需求，写入有效期 75 分钟的快照。worker 使用数据库 advisory lock，避免重叠批次。

## Backend Variables

```dotenv
DATABASE_URL=<Railway PostgreSQL reference>
REDIS_URL=<Railway Redis reference>
MODEL_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MODEL_API_KEY=<model key>
MODEL_INTENT=qwen-plus
MODEL_JUDGE=deepseek-v3
MODEL_AGENT=qwen-plus
MODEL_THINKING=disabled
JWT_SECRET=<strong random secret>
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
LANGSMITH_API_KEY=<LangSmith key>
LANGSMITH_PROJECT=faresniper
```

示例中的 provider key 故意留空，实际值只在 Railway Variables 中填写。`FLYAI_API_KEY` 与 `SERPAPI_API_KEY` 可分别缺省；缺少密钥只会把对应来源标记为 disabled，不阻止 API 启动。生产环境必须保持 `ENABLE_MOCK_FALLBACK=false`。

## Worker Variables

```dotenv
DATABASE_URL=<same Railway PostgreSQL reference>
REDIS_URL=<same Railway Redis reference>
CTRIP_SNAPSHOT_TTL_MINUTES=75
CTRIP_REFRESH_BATCH_SIZE=20
CTRIP_REQUEST_DELAY_MIN_SECONDS=2
CTRIP_REQUEST_DELAY_MAX_SECONDS=5
RUN_SCHEDULER_IN_API=false

LANGSMITH_TRACING=true
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_API_KEY=<LangSmith key>
LANGSMITH_PROJECT=faresniper
```

worker 不需要 `FLYAI_API_KEY` 或 `SERPAPI_API_KEY`。如启用现有价格告警推送，还需在 worker 配置对应的 VAPID/通知变量。

## Frontend Variables

```dotenv
NEXT_PUBLIC_API_BASE_URL=https://<backend>.up.railway.app
```

同时把 frontend 域名加入 backend 的 `CORS_ORIGINS`。

## FlyAI Runtime

`backend/nixpacks.toml` 在构建镜像时安装 Node.js 22 与全局固定版本 `@fly-ai/flyai-cli@1.0.16`。运行时直接执行 `flyai`，从环境读取 `FLYAI_API_KEY`；构建和请求路径都不执行 `npx`，也不执行 `flyai config set`。

下面命令安装的是兼容 coding-agent host 使用的 FlyAI skill 说明：

```bash
npx skills add alibaba-flyai/flyai-skill
```

它只适用于本地开发代理，不是 FareSniper 生产服务依赖。Railway 镜像直接安装官方 CLI，无需安装该 skill。

## 部署顺序

1. 部署 PostgreSQL/Redis，并给 backend 与 worker 关联变量。
2. 部署 backend，确认 migration 成功且 `/health` 可访问。
3. 部署 worker，确认 `ctrip_hourly_refresh` 按小时运行。
4. 部署 frontend，并更新 backend 的 `CORS_ORIGINS`。

## 验证

以下 `2099-08-01` 只是未来日期示例。该日期失效后，必须替换成执行当天之后的真实日期；城市参数使用中文全称。

先在 backend 容器确认固定 CLI 可用：

```bash
flyai --help
flyai search-flight --origin "北京" --destination "上海" --dep-date 2099-08-01 --sort-type 3
```

验证渐进 NDJSON 接口：

```bash
curl -N -X POST "https://<backend>/api/search/stream" \
  -H "Authorization: Bearer <session-token>" \
  -H "Content-Type: application/json" \
  -d '{"session_id":null,"message":"8月1日北京到上海"}'
```

只有在目标环境已经安全配置 provider key 时，才运行真实 smoke。命令只输出 `provider_statuses`、`deal_count`、`sellers`，不会输出 API key、完整预订 URL、raw offer 或 raw error：

```bash
python -m backend.scripts.verify_flight_providers \
  --origin 北京 --destination 上海 --depart-date 2099-08-01
python -m backend.scripts.verify_flight_providers \
  --origin 上海 --destination 新加坡 --depart-date 2099-08-01
```

预期摘要形状：

```json
{
  "provider_statuses": {"ctrip": "queued", "flyai": "success"},
  "deal_count": 3,
  "sellers": ["携程", "飞猪"]
}
```

LangSmith 项目 `faresniper` 只接收安全摘要。检查 `flight_search` 下适用的 `provider.flyai`、`provider.ctrip`、`provider.serpapi` 子 span，以及 worker 运行后的独立 `ctrip_hourly_refresh`；不得出现密钥、完整用户消息、raw offer、预订 URL 或第三方原始错误。

## 能力边界

- 国内航线使用 FlyAI 实时结果与携程小时快照；国际航线使用 FlyAI、SerpAPI 和匹配的携程快照。
- 搜索结果按来源渐进返回。单个 provider disabled、超时或失败不会阻止其他来源完成。
- FareSniper 展示报价并跳转到第三方销售平台，不在站内出票、支付或保证库存。
- 携程结果是 worker 快照，不等同于请求时实时抓取；超过 TTL 的结果不会获得实时最低价标记。
