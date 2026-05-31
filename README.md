# FareSniper

FareSniper 是一个面向自然语言机票搜索、低价发现和价格监控的全栈应用。用户可以直接输入「下周末北京去三亚，预算 600」这类口语化需求，系统会解析意图、补全槽位、查询航班与历史价格，并生成可执行的推荐结果。

## 核心能力

- 自然语言航班搜索：基于 LangGraph 工作流解析出发地、目的地、日期、预算和偏好。
- 低价推荐：结合平台价格、偏好匹配、历史价格和推荐评分生成前端卡片。
- 价格监控：支持告警、推送订阅、价格历史和定时任务。
- 用户记忆：保存常用偏好、查询历史和个性化推荐线索。
- 可观测性：支持 LangSmith trace、Langfuse prompt/score、延迟中间件和健康检查。
- Railway 部署：仓库内置 `railway.toml`，包含 backend、worker、frontend 三个服务入口。

## 技术栈

- Frontend: Next.js App Router, React, TypeScript, Tailwind CSS, Vitest
- Backend: FastAPI, Pydantic v2, SQLAlchemy async, Alembic, Redis, APScheduler
- Agent: LangGraph, LangChain, OpenAI-compatible chat model providers
- Observability: LangSmith tracing, Langfuse callback, structured health status
- Infra: Railway, PostgreSQL, Redis

## 目录结构

```text
backend/      FastAPI API、LangGraph workflow、数据库、任务调度、观测能力
frontend/     Next.js 前端应用、PWA、页面和组件
docs/         部署文档和阶段计划
scripts/      本地检查脚本
railway.toml  Railway 多服务启动配置
```

## 本地开发

### 后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn backend.main:app --reload
```

### 前端

```bash
cd frontend
npm install
npm run dev
```

前端默认通过 `/api/*` 代理到后端。生产环境可以设置：

```bash
NEXT_PUBLIC_API_BASE_URL=https://<your-backend>.up.railway.app
```

## 环境变量

后端变量参考 [backend/.env.example](backend/.env.example)。Railway 至少需要配置：

```bash
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://...
JWT_SECRET=<strong-secret>
MODEL_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MODEL_API_KEY=<provider-api-key>
MODEL_AGENT=qwen-plus
MODEL_INTENT=qwen-plus
MODEL_JUDGE=deepseek-v3
CORS_ORIGINS=["https://<frontend>.up.railway.app"]
```

### LangSmith Trace

部署时配置下面变量即可打开 LangSmith trace：

```bash
LANGSMITH_API_KEY=lsv2_...
LANGSMITH_PROJECT=faresniper
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_TRACING_V2=true
```

代码会自动把 `LANGSMITH_API_KEY` 映射到 LangChain tracing 所需的 `LANGCHAIN_API_KEY`，因此只配置 LangSmith 变量也可以产生日志链路。上线后访问 `/health`，返回里的 `langsmith_ok: true` 代表 trace 配置已生效。

### Langfuse

如果需要 prompt 版本化和打分写回，配置：

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

## Railway 部署

仓库根目录的 [railway.toml](railway.toml) 定义了三个服务：

- `backend`: 运行 Alembic migration 后启动 FastAPI。
- `worker`: 运行后台调度任务。
- `frontend`: 启动 Next.js production server。

推荐流程：

```bash
railway link
railway up
```

部署完成后检查：

```bash
curl https://<backend>.up.railway.app/health
```

关键字段应包含：

```json
{
  "graph_compiled": true,
  "scheduler_ok": true,
  "langsmith_ok": true
}
```

## 测试

```bash
pytest
npm --prefix frontend run lint
npm --prefix frontend test
```

## 相关文档

- [Architecture](ARCHITECTURE.md)
- [PRD](PRD.md)
- [Railway Deployment](docs/deployment/RAILWAY.md)
