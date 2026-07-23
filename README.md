# FareSniper

FareSniper 是一个自然语言机票搜索、比价和价格监控应用。用户输入航线、未来日期、预算和偏好后，后端会并行查询可用来源，并把来源状态、航班报价和第三方预订链接统一成同一套卡片与回复事实。

## 当前能力

- 中国机场目录：覆盖中国大陆 270 个、港澳台 18 个商业机场，共 288 个机场；城市名、机场名和 IATA 代码使用同一目录解析。
- 国内航线：FlyAI/飞猪实时结果与携程快照共同展示。
- 国际航线：FlyAI、SerpAPI Google Flights 和可匹配的携程快照共同展示。
- 事实一致性：卡片展示价、最低价分析、AI Markdown 和价格提醒建议都从冻结后的同一组报价生成。
- 渐进搜索：NDJSON 接口持续发送来源状态和结果；普通 JSON 搜索接口保持兼容。
- 价格监控：每 15 分钟主动刷新同航线报价，支持价格历史、Web Push、
  微信小程序订阅消息和可靠通知重试。
- 微信小程序：复用同一套搜索、推荐、记忆和监控 API，提供探索、对话、
  监控和我的四个核心页面。
- 安全观测：LangSmith 只记录 allowlist 摘要，不记录密钥、Cookie、原始第三方响应、完整预订 URL 或用户消息。

FareSniper 只负责搜索与比价，不在站内出票或支付。价格和库存以第三方预订页为准。

## 数据架构

```text
Browser -> Railway frontend -> Railway backend -> FlyAI / SerpAPI
                                      |
                                      +-> PostgreSQL demand queue/snapshots
                                                   ^
                                                   |
                                      macOS Ctrip collector

Railway worker -> demand seeding, alerts, scheduler
```

Railway 不运行 Chrome。携程登录、页面访问和 `batchSearch` 响应采集只在用户自己的 Mac 上进行；Mac 领取 Railway 中的航线任务，上传经过校验的结构化报价，Cookie 和专用 Chrome profile 始终留在本机。Railway worker 只维护需求队列、提醒和定时任务。

## 技术栈

- Frontend: Next.js App Router、React、TypeScript、Tailwind CSS、Vitest
- Mini Program: Taro 4、React、TypeScript、微信登录与订阅消息
- Backend: FastAPI、Pydantic v2、SQLAlchemy async、Alembic、Redis、APScheduler
- Agent: LangGraph、LangChain、OpenAI-compatible chat model
- Providers: FlyAI、携程 Mac collector、SerpAPI Google Flights
- Infra: Railway、PostgreSQL、Redis、LangSmith、Node.js 22

## 本地开发

后端：

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env
uvicorn backend.main:app --reload
```

FlyAI 需要 Node.js 22、`@fly-ai/flyai-cli@1.0.16` 和 `FLYAI_API_KEY`。生产请求直接调用固定版本的 `flyai`，不会运行 `npx` 或写全局 FlyAI 配置。

前端：

```bash
npm --prefix frontend install
npm --prefix frontend run dev
```

微信小程序：

```bash
cp miniprogram/.env.example miniprogram/.env
npm --prefix miniprogram install
npm --prefix miniprogram run typecheck
npm --prefix miniprogram run build:weapp
```

把 `miniprogram/project.config.json` 中的 `appid` 改成正式小程序 AppID 后，
使用微信开发者工具打开 `miniprogram/`。完整配置、订阅消息字段和发布步骤见
[WeChat Mini Program](docs/deployment/WECHAT_MINIPROGRAM.md)。

分离部署时设置：

```dotenv
NEXT_PUBLIC_API_BASE_URL=https://<backend>.up.railway.app
NEXT_PUBLIC_VAPID_PUBLIC_KEY=
```

## 配置

变量模板见 [`backend/.env.example`](backend/.env.example)。生产必须保持：

```dotenv
ENABLE_MOCK_FALLBACK=false
RUN_SCHEDULER_IN_API=false
FLYAI_API_KEY=
SERPAPI_API_KEY=
CTRIP_COLLECTOR_TOKEN=
LANGSMITH_API_KEY=
```

示例只保留空值。真实值只能进入本地未跟踪的环境文件或 Railway Variables。

LangSmith 使用手工安全 span：

```dotenv
FARESNIPER_LANGSMITH_TRACING=true
LANGSMITH_TRACING=false
LANGCHAIN_TRACING_V2=false
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGSMITH_PROJECT=faresniper
```

不要开启官方自动 tracing 开关；项目只通过局部 wrapper 发送已过滤摘要。

## 部署与采集

- Railway 服务、变量归属、migration 和验证：[Railway Deployment](docs/deployment/RAILWAY.md)
- Mac 携程登录、Clash、launchd、日志和恢复：[Mac Ctrip Collector](docs/deployment/MAC_CTRIP_COLLECTOR.md)
- 微信小程序、登录和价格订阅通知：[WeChat Mini Program](docs/deployment/WECHAT_MINIPROGRAM.md)

## 测试

```bash
python -m pytest backend/tests -q
npm --prefix frontend test -- --run
npm --prefix frontend run build
npm --prefix miniprogram run typecheck
npm --prefix miniprogram run build:weapp
```

默认测试不调用付费来源。配置好 Railway、JWT 和 Mac collector 后，可对未来日期运行：

```bash
DEPART_DATE="$(python -c 'from datetime import date, timedelta; print(date.today() + timedelta(days=14))')"

python -m backend.scripts.verify_live_fares \
  --origin 阿勒泰 \
  --destination 三亚 \
  --depart-date "$DEPART_DATE" \
  --require-fresh
```

脚本只输出状态、币种/价格和固定 trace 名称，不输出密钥或预订 URL。JWT 的安全获取与清理命令见 [Railway Deployment](docs/deployment/RAILWAY.md#验证)。

## 相关文档

- [Architecture](ARCHITECTURE.md)
- [PRD](PRD.md)
- [Railway Deployment](docs/deployment/RAILWAY.md)
- [Mac Ctrip Collector](docs/deployment/MAC_CTRIP_COLLECTOR.md)
- [WeChat Mini Program](docs/deployment/WECHAT_MINIPROGRAM.md)
