# Railway 部署清单

## 服务

- **backend**：FastAPI（含 `alembic -c backend/alembic.ini upgrade head` 启动钩子）
- **worker**：APScheduler（每小时全量爬取 + 每 15 分钟告警扫描）
- **frontend**：Next.js standalone

## 必填环境变量

```
DATABASE_URL
REDIS_URL
MODEL_BASE_URL
MODEL_API_KEY
MODEL_AGENT
MODEL_JUDGE
MODEL_THINKING
JWT_SECRET
VAPID_PRIVATE_KEY
VAPID_SUBJECT
LANGFUSE_PUBLIC_KEY
LANGFUSE_SECRET_KEY
LANGFUSE_HOST
LANGSMITH_API_KEY
LANGSMITH_PROJECT
FLIGHT_STATUS_API_URL
FLIGHT_STATUS_API_KEY
CPS_ID_DEFAULT
```

## 灰度策略

终态：默认 100% 流量打开。如需下线某能力，通过 `feature_flags` 表更新 `rollout_pct=0` 即可。
