# FareSniper API Contract

本文件是前后端并行开发时的唯一接口约定，适用于当前阶段的 FastAPI 后端和 Next.js 前端联调。

## 0. Status

这是本次并行开发的目标契约，当前仓库里的后端实现还没有完全对齐本文件。
后续以本文件为准推进改造，而不是以现有 mock 字段或旧接口返回为准。

## 1. 协作原则

- 所有联调接口统一挂在 `/api` 下。
- 线上传输的 JSON 字段统一使用 `snake_case`。
- 前端内部页面组件可以继续使用 `camelCase`，但只能在 `api-client` 或数据适配层做转换。
- 后端负责业务判断和结构化字段，前端负责视觉字段，例如渐变色、卡片旋转角度、文案排版。
- 暂未接入正式登录前，所有接口继续显式传 `user_id`，默认值为 `demo-user`。

## 2. 通用约定

### 2.1 Base URL

- 本地后端：`http://localhost:8000`
- API 前缀：`/api`
- 例如：`POST http://localhost:8000/api/search`

### 2.2 数据格式

- 请求和响应统一使用 `application/json`
- 金额单位统一为人民币元，使用整数，例如 `398`
- 日期统一使用 `YYYY-MM-DD`
- 时间戳统一使用 ISO 8601 UTC，例如 `2026-04-11T09:30:00Z`

### 2.3 错误响应

后端统一返回：

```json
{
  "error": {
    "code": "INVALID_QUERY",
    "message": "destination is required",
    "details": {}
  }
}
```

推荐错误码：

- `INVALID_QUERY`
- `UNAUTHORIZED`
- `NOT_FOUND`
- `UPSTREAM_UNAVAILABLE`
- `INTERNAL_ERROR`

## 3. 核心 DTO

### 3.1 DealCardDTO

用于 `/api/search` 和 `/api/recommendations` 的机票卡片统一结构。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | `string` | 业务唯一 ID |
| `system_id` | `string` | 展示给前端的系统编号，例如 `SYS.042` |
| `platform` | `string` | 数据来源平台，例如 `ctrip` |
| `origin_city` | `string` | 出发城市中文名 |
| `origin_code` | `string` | 出发地三字码，例如 `BJS` |
| `destination_city` | `string` | 到达城市中文名 |
| `destination_code` | `string` | 到达地三字码，例如 `SYX` |
| `depart_date` | `string` | 出发日期 |
| `airline` | `string` | 航司名称 |
| `depart_time` | `string` | 起飞时间，格式 `HH:mm` |
| `arrive_time` | `string` | 到达时间，格式 `HH:mm` |
| `price` | `number` | 当前价格 |
| `original_price` | `number \| null` | 参考原价或均价，没有则为 `null` |
| `discount_rate` | `number \| null` | 折扣百分比，整数，例如 `59` 表示便宜 59% |
| `cabin` | `string \| null` | 舱位 |
| `signals` | `string[]` | 值得买信号 |
| `confidence` | `'high' \| 'medium' \| 'low'` | 置信度 |
| `verdict` | `string` | 卡片级结论，例如 `建议现在买` |
| `booking_url` | `string \| null` | 跳转购买链接，可为空 |

### 3.2 SearchQueryDTO

| 字段 | 类型 | 说明 |
|---|---|---|
| `raw_text` | `string` | 用户原始输入 |
| `normalized_text` | `string` | 后端归一化后的输入 |
| `origin_city` | `string` | 出发城市 |
| `origin_code` | `string` | 出发地三字码 |
| `destination_city` | `string` | 目的地城市 |
| `destination_code` | `string` | 目的地三字码 |
| `date_start` | `string` | 查询起始日期 |
| `date_end` | `string` | 查询结束日期 |
| `budget` | `number \| null` | 预算上限 |

### 3.3 SearchRecommendationDTO

| 字段 | 类型 | 说明 |
|---|---|---|
| `action` | `'buy_now' \| 'watch' \| 'skip'` | 机器可读结论 |
| `text` | `string` | 展示文案，例如 `建议现在买` |
| `confidence` | `'high' \| 'medium' \| 'low'` | 置信度 |
| `signals` | `string[]` | 结论依据 |

### 3.4 MemoryItemDTO

`field` 先约定为以下几类：

- `price_anchor`
- `preferred_origins`
- `preferred_destinations`
- `travel_window`
- `cabin_preference`

结构如下：

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | `string` | 记忆项唯一 ID，当前可直接用 `field` |
| `field` | `string` | 机器字段名 |
| `label` | `string` | 展示名，例如 `心理价位` |
| `value` | `string \| number \| string[]` | 原始值 |
| `value_display` | `string` | 给前端直接展示的文案 |
| `source` | `'manual' \| 'auto'` | 来源 |
| `updated_at` | `string` | 更新时间 |

### 3.5 RecommendationCardDTO

用于首页或无明确查询时的推荐卡片。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | `string` | 卡片 ID |
| `title` | `string` | 标题 |
| `reason` | `string` | 推荐原因 |
| `query_hint` | `string` | 点击后回填到对话框的提示词 |
| `tags` | `string[]` | 标签 |
| `preview_deal` | `DealCardDTO \| null` | 可选预览票卡 |

## 4. 接口定义

### 4.1 `GET /health`

响应：

```json
{
  "status": "ok",
  "app": "Flight Deals Backend"
}
```

### 4.2 `POST /api/search`

用途：

- 对话页提交自然语言搜索
- 探索页展示搜索结果

请求：

```json
{
  "user_id": "demo-user",
  "message": "五一去三亚，预算600以内"
}
```

响应：

```json
{
  "user_id": "demo-user",
  "query": {
    "raw_text": "五一去三亚，预算600以内",
    "normalized_text": "五一去三亚，预算600以内",
    "origin_city": "北京",
    "origin_code": "BJS",
    "destination_city": "三亚",
    "destination_code": "SYX",
    "date_start": "2026-05-01",
    "date_end": "2026-05-03",
    "budget": 600
  },
  "deals": [
    {
      "id": "fd001",
      "system_id": "SYS.042",
      "platform": "ctrip",
      "origin_city": "北京",
      "origin_code": "BJS",
      "destination_city": "三亚",
      "destination_code": "SYX",
      "depart_date": "2026-05-01",
      "airline": "海南航空",
      "depart_time": "07:30",
      "arrive_time": "13:45",
      "price": 398,
      "original_price": 980,
      "discount_rate": 59,
      "cabin": "经济舱",
      "signals": ["近90天低位", "五一低价"],
      "confidence": "high",
      "verdict": "建议现在买",
      "booking_url": null
    }
  ],
  "analysis": {
    "min_price": 398,
    "max_price": 620,
    "avg_price": 510,
    "avg_90d": 705,
    "lower_than_avg": 0.44,
    "price_spread_pct": 0.56,
    "match_score": 0.92,
    "within_budget": true,
    "matched_preferences": ["price_anchor", "preferred_destinations"]
  },
  "recommendation": {
    "action": "buy_now",
    "text": "建议现在买",
    "confidence": "high",
    "signals": ["近90天低位", "符合心理价位"]
  },
  "meta": {
    "request_id": "srh_20260411_001",
    "source": "ctrip",
    "result_count": 5,
    "fallback_mode": false,
    "generated_at": "2026-04-11T09:30:00Z"
  }
}
```

实现要求：

- `deals` 已按 `price` 升序排序
- `deals[*].verdict` 和 `deals[*].confidence` 当前阶段允许直接复用顶层 `recommendation`
- `matched_preferences` 返回命中的 `field` 列表，不返回中文文案

### 4.3 `GET /api/memory?user_id=demo-user`

用途：

- 我的记忆页首屏加载

响应：

```json
{
  "user_id": "demo-user",
  "memories": [
    {
      "id": "price_anchor",
      "field": "price_anchor",
      "label": "心理价位",
      "value": 600,
      "value_display": "¥600 以内",
      "source": "manual",
      "updated_at": "2026-04-10T10:30:00Z"
    },
    {
      "id": "preferred_destinations",
      "field": "preferred_destinations",
      "label": "想去的地方",
      "value": ["三亚", "大理", "成都"],
      "value_display": "三亚、大理、成都",
      "source": "auto",
      "updated_at": "2026-04-11T09:10:00Z"
    }
  ],
  "query_history": [],
  "click_history": [],
  "meta": {
    "generated_at": "2026-04-11T09:30:00Z"
  }
}
```

说明：

- 前端记忆页直接消费 `memories`
- `label` 和 `value_display` 由后端返回，避免前端重复维护业务字典
- `query_history`、`click_history` 先保留原样，当前页面不强依赖

### 4.4 `PATCH /api/memory`

用途：

- 编辑某条偏好
- 添加某条偏好

请求：

```json
{
  "user_id": "demo-user",
  "field": "price_anchor",
  "value": 500,
  "source": "manual"
}
```

响应：

- 返回最新的完整 `GET /api/memory` 响应，便于前端直接刷新本地状态

### 4.5 `DELETE /api/memory/{field}?user_id=demo-user`

用途：

- 删除某条偏好

响应：

- 返回最新的完整 `GET /api/memory` 响应

说明：

- 当前前端记忆页已有删除动作，因此该接口纳入正式契约
- 如果后端暂时不支持真实删除，至少要支持把对应字段从 `memories` 中移除

### 4.6 `GET /api/recommendations?user_id=demo-user`

用途：

- 首页首屏推荐
- 无查询时的推荐卡片

响应：

```json
{
  "user_id": "demo-user",
  "cards": [
    {
      "id": "rec_001",
      "title": "热门低价机会",
      "reason": "适合拿来做首页首屏展示",
      "query_hint": "五一去三亚，600以内",
      "tags": ["热门", "低价"],
      "preview_deal": {
        "id": "fd001",
        "system_id": "SYS.042",
        "platform": "ctrip",
        "origin_city": "北京",
        "origin_code": "BJS",
        "destination_city": "三亚",
        "destination_code": "SYX",
        "depart_date": "2026-05-01",
        "airline": "海南航空",
        "depart_time": "07:30",
        "arrive_time": "13:45",
        "price": 398,
        "original_price": 980,
        "discount_rate": 59,
        "cabin": "经济舱",
        "signals": ["近90天低位", "五一低价"],
        "confidence": "high",
        "verdict": "建议现在买",
        "booking_url": null
      }
    }
  ],
  "meta": {
    "source": "memory+mock",
    "generated_at": "2026-04-11T09:30:00Z"
  }
}
```

## 5. 页面和接口的对应关系

### `/chat`

- 输入框提交后调用 `POST /api/search`
- 不在页面组件里直接解析意图
- 建议把搜索结果存到页面状态或全局状态，再跳 `/explore`

### `/explore`

- 主要消费 `POST /api/search` 的 `deals`
- 卡片上的渐变色、hover 动效、筛选 UI 由前端自行控制
- 如果要支持“今日精选”模式，可额外消费 `GET /api/recommendations`

### `/memory`

- 首屏读取 `GET /api/memory`
- 编辑走 `PATCH /api/memory`
- 删除走 `DELETE /api/memory/{field}`

### `/`

- 当前登录页和预览卡可以先继续用 mock
- 若要接真数据，优先接 `GET /api/recommendations`

## 6. 前后端分工边界

### 后端负责

- 维护本文件中的真实响应结构
- 返回稳定字段和机器可读枚举
- 返回 `label`、`value_display`、`signals`、`action` 这类业务判断结果

### 前端负责

- 只通过 `api-client` 访问后端
- 在 `api-client` 内把 DTO 转成现有 UI 类型，例如 `FlightDeal`、`PreferenceMemory`
- 维护视觉样式字段，例如 `gradientFrom`、`gradientTo`、`accentColor`、`rotation`

## 7. 当前版本要点

这次接口约定相对现有代码有 4 个明确收敛点：

1. 搜索结果统一输出 `deals`，直接服务探索页卡片，而不是只给原始 `flights`
2. 推荐结论统一拆成 `action + text + confidence`，避免前端只拿一句中文文案做逻辑判断
3. 记忆接口统一输出 `memories`，并补上 `label`、`value_display`
4. 正式纳入 `DELETE /api/memory/{field}`，覆盖前端现有删除交互

如果后续要新增字段，以“只增不改”为原则；如果要改字段名，优先升级本文件，再改代码。
