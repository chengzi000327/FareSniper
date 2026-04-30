# 特价机票发现平台 PRD

## 1. 基本信息

| 项目 | 说明 |
|------|------|
| 功能名称 | 特价机票发现平台 |
| 所属模块 | 全产品 |
| 版本号 | v1.1 |
| 负责人 | [待填] |
| 预计上线时间 | [待填] |

## 2. 更新记录

| 时间 | 作者 | 更新说明 |
|------|------|----------|
| 2026-04-11 | | 初稿 |
| 2026-04-17 | | 按 prd-writer 规范重写，补全 Agent State、Prompt 设计、字段定义 |
| 2026-04-18 | | 补全 API 接口规范（5个接口）、完整 DTO 定义、前端页面数据流（4个页面）|
| 2026-04-18 | | 补充 user_id 生命周期、session 多轮对话、价格监控 MVP、recommend_score 计算规则、deals 排序规则、统一新用户阈值，记忆存储改为纯后端 DB |
| 2026-04-19 | | 确认所有待定决策：booking_url 深链规则、节假日写死规则、history_avg_90d 随机浮动、追问降级 Modal 浮层、PreferenceMatch 改纯工程规则、模型改环境变量配置支持国内模型 |

---

## 3. 功能概述

- **背景**：价格敏感的年轻出行者（18-30岁）找便宜机票需要在5个以上平台反复切换，平均耗时30-60分钟，买完仍无法确认"这是不是真的便宜"。5人用户访谈证实核心痛点是多平台切换效率低、缺乏客观判断标准。
- **目标用户**：18-30岁价格敏感出行者，学生 / 应届毕业生 / 背包客为主，出行频率1-5次/年，习惯多平台比价，愿意为省100元货比三家。
- **功能介绍**：对话式入口聚合多平台机票价格，结合用户偏好记忆输出「值得买」判断，让用户在一个界面完成查票决策闭环。
- **目标收益**：查询→结果→跳转购买流程完成率 > 40%；AI建议采纳率 > 30%；单次决策时间从30-60分钟压缩至 < 5分钟。

---

## 4. 流程定义

### 4.1 业务流程

<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 680 680" style="font-family:system-ui,sans-serif;max-width:680px;width:100%">
<defs>
  <style>
    .th{font-size:13px;font-weight:600;fill:#111827}
    .ts{font-size:11px;fill:#6b7280}
    .c-gray{fill:#f3f4f6;stroke:#9ca3af;stroke-width:1.5}
    .c-teal{fill:#ccfbf1;stroke:#0d9488;stroke-width:1.5}
    .c-blue{fill:#dbeafe;stroke:#2563eb;stroke-width:1.5}
    .c-amber{fill:#fef3c7;stroke:#d97706;stroke-width:1.5}
    .c-red{fill:#fee2e2;stroke:#ef4444;stroke-width:1.5}
    .c-blue-dash{fill:#dbeafe;stroke:#2563eb;stroke-width:1.5;stroke-dasharray:5,3}
    .edge{fill:none;stroke:#9ca3af;stroke-width:1.5;marker-end:url(#arrow)}
    .lbl{font-size:11px;fill:#6b7280}
  </style>
  <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
    <path d="M2 1L8 5L2 9" fill="none" stroke="#9ca3af" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
  </marker>
</defs>

<!-- 1. 用户输入 -->
<rect x="250" y="14" width="180" height="36" rx="18" class="c-gray"/>
<text x="340" y="32" text-anchor="middle" dominant-baseline="central" class="th">用户自然语言输入</text>

<line x1="340" y1="50" x2="340" y2="83" class="edge"/>

<!-- 2. 意图理解 -->
<rect x="195" y="83" width="290" height="36" rx="8" class="c-teal"/>
<text x="340" y="101" text-anchor="middle" dominant-baseline="central" class="th">意图理解 Agent（LLM）</text>

<line x1="340" y1="119" x2="340" y2="152" class="edge"/>

<!-- 3. 信息完整？ diamond -->
<polygon points="340,150 408,174 340,198 272,174" class="c-amber"/>
<text x="340" y="174" text-anchor="middle" dominant-baseline="central" class="th">信息完整？</text>

<!-- 不完整 → 追问 -->
<path d="M408 174 L450 174" class="edge"/>
<text x="416" y="166" class="lbl">不完整</text>
<rect x="450" y="156" width="120" height="36" rx="8" class="c-red"/>
<text x="510" y="174" text-anchor="middle" dominant-baseline="central" class="th">追问用户</text>
<!-- 追问 → 回用户输入 右侧绕行 -->
<path d="M570 156 L618 156 L618 32 L430 32" class="edge" stroke-dasharray="4,2"/>
<text x="628" y="95" class="lbl" transform="rotate(90,628,95)">最多2次</text>

<!-- 完整 → 向下分叉 -->
<path d="M340 198 L340 235" class="edge"/>
<text x="348" y="222" class="lbl">完整</text>

<!-- 分叉横线 -->
<line x1="155" y1="235" x2="525" y2="235" stroke="#9ca3af" stroke-width="1.5"/>

<!-- 4a. 比价Agent -->
<line x1="155" y1="235" x2="155" y2="263" class="edge"/>
<rect x="50" y="263" width="210" height="36" rx="8" class="c-blue"/>
<text x="155" y="281" text-anchor="middle" dominant-baseline="central" class="th">比价 Agent（工程）</text>

<!-- 4b. 偏好匹配 -->
<line x1="525" y1="235" x2="525" y2="263" class="edge"/>
<rect x="400" y="263" width="250" height="36" rx="8" class="c-teal"/>
<text x="525" y="281" text-anchor="middle" dominant-baseline="central" class="th">偏好匹配 Agent（LLM）</text>

<!-- 汇聚到判断Agent -->
<path d="M155 299 L155 358 L300 358" class="edge"/>
<path d="M525 299 L525 358 L380 358" class="edge"/>

<!-- 5. 判断Agent -->
<rect x="195" y="358" width="290" height="36" rx="8" class="c-teal"/>
<text x="340" y="376" text-anchor="middle" dominant-baseline="central" class="th">判断 Agent（LLM）</text>

<line x1="340" y1="394" x2="340" y2="427" class="edge"/>

<!-- 6. 生成结果 -->
<rect x="210" y="427" width="260" height="36" rx="8" class="c-blue"/>
<text x="340" y="445" text-anchor="middle" dominant-baseline="central" class="th">生成结果</text>

<!-- 分叉 -->
<path d="M340 463 L340 497" stroke="#9ca3af" stroke-width="1.5" fill="none"/>
<line x1="155" y1="497" x2="525" y2="497" stroke="#9ca3af" stroke-width="1.5"/>

<!-- 7a. 输出给用户 -->
<line x1="155" y1="497" x2="155" y2="527" class="edge"/>
<rect x="40" y="527" width="230" height="36" rx="8" class="c-blue"/>
<text x="155" y="545" text-anchor="middle" dominant-baseline="central" class="th">输出结果给用户</text>

<!-- 7b. 记忆更新 -->
<line x1="525" y1="497" x2="525" y2="527" class="edge"/>
<rect x="395" y="527" width="250" height="36" rx="8" class="c-blue-dash"/>
<text x="520" y="545" text-anchor="middle" dominant-baseline="central" class="th">异步记忆更新</text>

<!-- 汇聚END -->
<path d="M155 563 L155 634 L300 634" class="edge"/>
<path d="M525 563 L525 634 L380 634" class="edge"/>
<text x="535" y="600" class="ts">失败不阻塞主流程</text>

<!-- 8. END -->
<rect x="260" y="622" width="160" height="36" rx="18" class="c-gray"/>
<text x="340" y="640" text-anchor="middle" dominant-baseline="central" class="th">END</text>
</svg>

### 4.2 节点说明

| Node | 类型 | 流转（Edge） | 备注 |
|------|------|-------------|------|
| 用户自然语言输入 | 工程 | → 意图理解 | 无格式限制，支持文本输入 |
| 意图理解 Agent | LLM | 成功 → 信息完整判断；解析失败 → END（兜底提示） | 解析出发地/目的地/时间/预算/约束 |
| 信息完整？ | 工程 | 完整 → 并行执行；不完整 → 追问 | 必填：出发地、目的地、时间范围 |
| 追问用户 | 工程 | → 用户输入 | 最多追问2次，超限降级为结构化表单 |
| 比价 Agent | 工程 | → 判断 Agent | 并行查询多平台，单平台超时3s跳过 |
| 偏好匹配 Agent | LLM+工程 | → 判断 Agent | 读取用户偏好记忆，计算每条结果的匹配度 |
| 判断 Agent | LLM | → 生成结果 | 综合价格+历史均价+偏好，输出值得买信号 |
| 生成结果 | 工程 | → 输出给用户 + 异步记忆更新 | 记忆更新异步执行，不阻塞主链路 |
| 异步记忆更新 | 工程 | → END | 写入失败静默忽略，不影响主流程 |

---

## 5. 功能点详细说明

### 5.1 Agent State 设计

| 分类 | 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|------|
| 基础 | user_id | string | 是 | 用户ID，由后端分配匿名ID，见5.8 |
| 基础 | session_id | string | 是 | 对话会话ID，后端维护多轮上下文，见5.9 |
| 基础 | message | string | 是 | 用户当前输入的原始文本 |
| 意图 | intent | object | 是 | 解析出的结构化意图，见5.2 |
| 意图 | intent_complete | boolean | 是 | 必填字段是否齐全，conditional edge 用于路由判断 |
| 意图 | clarify_count | integer | 是 | 已追问次数，默认0，≥2次触发表单降级 |
| 价格 | price_results | array | 否 | 各平台价格列表，见5.3 |
| 偏好 | user_memory | object | 否 | 用户偏好记忆快照，见5.5 |
| 偏好 | preference_matched | array | 否 | 每条结果的偏好匹配结果 |
| 控制 | fallback_triggered | boolean | 是 | 是否已触发降级，默认false |

> **注**：`trace_id` 由 LangSmith 在每次 `graph.invoke()` 时自动生成 `run_id`，无需注入 State。防死循环改用 LangGraph 原生 `recursion_limit`（默认15），通过 `graph.invoke(config={"recursion_limit": 15})` 传入，不放入 State。

### 5.2 意图识别

**必须解析的字段：**

| 字段 | 类型 | 必填 | 说明 | 缺失时行为 |
|------|------|------|------|-----------|
| origin | string | 是 | 出发城市（中文） | 追问 |
| destination | string | 是 | 目的地城市（中文） | 追问 |
| date_range | object | 是 | `{start: "YYYY-MM-DD", end: "YYYY-MM-DD"}` | 追问 |
| budget | integer | 否 | 单程预算上限（元），null表示不限 | 不追问 |
| constraints | array | 否 | 约束条件枚举值列表，见下表 | 不追问 |

**约束条件枚举：**

| 枚举值 | 触发词 | 说明 |
|--------|--------|------|
| avoid_redeye | "不要太早"/"不要红眼" | 起飞时间须 ≥ 06:00 |
| direct_only | "直飞" | 不展示中转航班 |
| prefer_morning | "早点到" | 优先到达时间在12:00前的航班 |

**追问逻辑：**
1. origin 缺失 → "请问您从哪个城市出发？"
2. destination 缺失 → "请问目的地是哪里？"
3. date_range 缺失 → "请问什么时间出发？"
4. clarify_count ≥ 2 且仍不完整 → 降级为结构化表单（**Modal 浮层弹出**，不跳页）

**时间表述映射（模型推算，提供兜底映射表）：**

| 表述 | 映射规则 |
|------|---------|
| 五一 | 2026-05-01 ~ 2026-05-05 |
| 清明 | 2026-04-04 ~ 2026-04-06 |
| 国庆 | 2026-10-01 ~ 2026-10-07 |
| 下周末 | 最近的周六~周日 |
| 本周末 | 本周六~周日 |

### 5.3 比价技能

MVP阶段使用Mock数据，接口层预留真实API扩展位。

**Mock数据覆盖范围：**
- 至少5条高频航线：北京↔成都、北京↔三亚、北京↔上海、北京↔广州、北京↔杭州
- 每条航线每天2-3个航班，每个航班覆盖3个平台（携程/去哪儿/飞猪）
- 平台间价差模拟真实情况（通常±5%-15%）
- 包含近90天历史均价和历史最低价字段（`history_avg_90d = lowest_price × random(1.2, 1.5)`，`history_low_90d = lowest_price × random(0.8, 0.95)`，Mock 时随机生成）

**返回字段结构：**

```json
{
  "flight_no": "HU7833",
  "airline": "海南航空",
  "dep_time": "09:30",
  "arr_time": "14:20",
  "duration": "4h50m",
  "stops": 0,
  "prices": [
    {"platform": "携程", "price": 389, "url": "https://..."},
    {"platform": "去哪儿", "price": 399, "url": "https://..."},
    {"platform": "飞猪", "price": 410, "url": "https://..."}
  ],
  "lowest_price": 389,
  "history_avg_90d": 584,
  "history_low_90d": 312
}
```

**超时处理：**

| 场景 | 处理方式 |
|------|---------|
| 单个平台超时（>3s） | 跳过该平台，用已有结果继续 |
| 全部平台超时 | 返回空数组，前端展示"暂无数据，请重试" |
| Mock数据无匹配航线 | 返回空数组 |

### 5.4 偏好匹配技能

读取用户偏好记忆，对每条航班结果逐条计算匹配情况。

**匹配规则：**

| 偏好类型 | 匹配条件 | 输出文案 |
|---------|---------|---------|
| 心理价位 | lowest_price ≤ user.budget | ✓ 在你的心理价位以内 |
| 避免红眼 | dep_time ≥ "06:00" 且 user有avoid_redeye | ✓ 符合你的出行习惯 |
| 偏好航司 | airline in user.preferred_airlines | ✓ 你常飞的[航司名] |
| 常去城市 | destination in user.frequent_cities | 不输出文案，仅影响排序权重（靠前） |

**新用户处理（memories 列表为空时）：**
- preference_matched 返回空数组
- 判断节点跳过偏好维度，结果卡片不展示偏好相关文案
- 个人中心的「根据你的偏好」卡片隐藏
- 判断标准：直接检查后端 memories 是否为空，不依赖 query_count

### 5.5 记忆设计

**存储位置：后端数据库（PostgreSQL）**

所有用户偏好和历史数据存在后端 DB，通过 `/api/memory` 系列接口读写。前端不直接读写 localStorage 存偏好，只在 localStorage 里缓存 `user_id`（见 5.8）。

**后端存储的记忆字段：**

| field | 类型 | 说明 |
|-------|------|------|
| budget | number | 心理价位（元） |
| frequent_cities | string[] | 常去城市列表 |
| preferred_airlines | string[] | 偏好航司列表 |
| constraints | string[] | 出行习惯枚举 |
| travel_scenes | string[] | 出行场景枚举 |
| query_history | object[] | 搜索历史（含 text + created_at） |
| click_history | object[] | 点击历史（含 flight_info + created_at） |

**记忆更新逻辑（异步，用户不感知）：**

| 用户行为 | 更新字段 | 更新规则 |
|---------|---------|---------|
| 查询某目的地 | frequent_cities | 同一城市出现 ≥3次 → 加入列表 |
| 点击某张票 | budget | 取最近5次点击价格的中位数（四舍五入到整十） |
| 多次查询非红眼时段 | constraints | 连续3次查询dep_time≥06:00 → 推断avoid_redeye |
| 点击某航司的票 | preferred_airlines | 同一航司点击 ≥2次 → 加入列表 |

**个人中心用户可操作项：**
- 查看所有偏好条目（5类：常去城市、心理价位、偏好航司、出行习惯、出行场景）
- 每条偏好可逐条编辑
- 「清除所有记忆」一键重置，并弹出确认弹窗（不可逆操作）

### 5.6 值得买信号体系

**判断逻辑（按优先级）：**

| 信号 | 触发条件 | 展示文案 |
|------|---------|---------|
| 历史低价 | lowest_price < history_avg_90d × 0.85 | 🔥 近90天最低，比均价低X% |
| 节假日稀缺 | 出行日为法定节假日（`is_holiday=true`）| ⚡ 节假日难得低价（**MVP 前端不渲染该标签，`is_holiday` 仍传入 ValueJudge 供 advice 文案参考，signals 数组中不输出该值**）|
| 符合心理价位 | lowest_price ≤ user.budget | ✓ 在你的心理价位以内 |
| 符合出行习惯 | 见偏好匹配表 | ✓ 符合你的出行习惯 |

**一句话购买建议生成规则：**

| 触发信号组合 | advice 文案（≤20字） |
|------------|---------------------|
| 历史低价 + 符合心理价位 | 建议现在买，比均价低X%且在预算内 |
| 历史低价，但超预算 | 历史低位，但超出预算X元 |
| 仅符合心理价位，价格正常 | 在预算内，价格正常可继续关注 |
| 无信号触发 | 价格正常，可继续关注 |
| 历史数据不足 | 数据有限，仅供参考 |

### 5.7 异常处理

| 异常场景 | 触发条件 | 处理方式 |
|---------|---------|---------|
| 意图解析失败 | LLM返回非法JSON | 展示"没听明白，换个说法试试？"，提供表单入口 |
| 比价数据为空 | 全平台超时/无匹配航线 | 展示"暂未找到航班，试试换个日期" |
| 偏好记忆读取失败 | 后端 /api/memory 接口失败 | 跳过偏好维度，正常展示价格结果，不报错 |
| 判断Agent超时（>5s） | LLM响应超时 | 跳过AI建议，仅展示价格数据，结论位置展示"分析中…" |
| 记忆写入失败 | 后端 DB 写入异常 | 静默忽略，下次查询时重试 |
| 追问超限 | clarify_count ≥ 2 | 降级到结构化表单，展示"填一下这几项吧" |

### 5.8 用户身份（user_id）生命周期

**分配方式：后端分配匿名 ID，通过首次 API 响应下发**

1. 用户首次访问，前端发任意 API 请求（或初始化时调 `POST /api/session/init`）
2. 后端检测请求中无有效 user_id → 生成 UUID 并写入响应体
3. 前端收到 user_id 后存入 `localStorage`（key = `faresnipper_user_id`）
4. 后续所有请求从 localStorage 读取 user_id 携带到请求体中

**前端伪代码：**

```typescript
function getUserId(): string {
  let id = localStorage.getItem('faresnipper_user_id')
  if (!id) {
    // 等待首次 API 返回后再存，或先用临时 ID
  }
  return id ?? 'pending'
}
```

**约束：**
- MVP 不做账号体系，user_id 是匿名标识，换浏览器/设备后数据不共享
- user_id 只要 localStorage 不被清除就持续有效
- 后端收到未知 user_id 时，自动创建新用户数据，不报错

### 5.9 多轮对话（session）设计

**机制：后端维护 session，前端传 session_id**

| 步骤 | 行为 |
|------|------|
| 用户点击「历史对话」清空或开始新话题 | 前端调 `POST /api/session` 获取新 session_id |
| 用户每次发消息 | POST /api/search 请求体携带 session_id |
| 后端收到 session_id | 查询该 session 的历史消息，拼入 IntentParser 上下文 |
| 追问场景 | 后端在 session 历史里找到上一轮缺失字段，追问只补缺失项 |
| session 过期 | 超过 30 分钟无活动后 session 失效；前端下次请求时后端返回 session_expired 错误，前端自动创建新 session |

**新增接口：POST /api/session**

```json
请求：{ "user_id": "xxx" }
响应：{ "session_id": "uuid", "created_at": "..." }
```

**POST /api/search 请求体更新（加 session_id）：**

```json
{
  "user_id": "xxx",
  "session_id": "yyy",
  "message": "五一去三亚，预算600"
}
```

### 5.10 价格监控（MVP 基础版）

用户在航班卡片点击「监控价格」，后端记录该监控意图。MVP 阶段不做实时推送，仅存储监控列表，供个人中心展示。

**交互流程：**
1. 用户点击卡片上「监控价格」按钮
2. 前端调 `POST /api/alerts`，传入航班信息 + 用户当前出价（最低价）
3. 后端存储监控记录，返回成功
4. 个人中心「价格监控」节点调 `GET /api/alerts` 展示监控列表

**POST /api/alerts 请求：**

```json
{
  "user_id": "xxx",
  "flight_id": "HU7833-20260501",
  "origin_city": "北京",
  "destination_city": "三亚",
  "depart_date": "2026-05-01",
  "current_price": 449,
  "target_price": 400
}
```

**POST /api/alerts 响应：**

```json
{
  "alert_id": "alert-uuid",
  "status": "active",
  "created_at": "2026-04-18T10:00:00Z"
}
```

**GET /api/alerts 响应：**

```json
{
  "user_id": "xxx",
  "alerts": [
    {
      "alert_id": "alert-uuid",
      "origin_city": "北京",
      "destination_city": "三亚",
      "depart_date": "2026-05-01",
      "current_price": 449,
      "target_price": 400,
      "status": "active",
      "created_at": "2026-04-18T10:00:00Z"
    }
  ]
}
```

**MVP 限制：**
- 不做实时价格追踪和推送通知
- 只展示监控列表，不判断是否达到目标价
- 用户可查看已创建的监控（GET /api/alerts），不可编辑
- DELETE /api/alerts/{alert_id} 支持取消监控（v1.1 实现）

---

## 6. Prompt 设计

### Prompt 汇总

| Prompt 名称 | 用途 | 调用节点 | 模型 |
|------------|------|---------|------|
| IntentParser | 自然语言意图解析 | 意图理解节点 | 环境变量 `MODEL_INTENT`，默认国内模型，见下方说明 |
| PreferenceMatch | 偏好匹配度计算 | 偏好匹配节点 | **无 LLM，改为纯工程规则**，见 6.2 |
| ValueJudge | 值得买信号+建议生成 | 判断节点 | 环境变量 `MODEL_JUDGE`，默认国内模型，见下方说明 |

**模型配置说明（国内部署）：**

```bash
# 后端环境变量配置（支持任意兼容 OpenAI Chat Completions API 的国内模型）
MODEL_INTENT=qwen-turbo         # IntentParser 使用，追求低延迟
MODEL_JUDGE=qwen-plus           # ValueJudge 使用，追求质量
MODEL_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
MODEL_API_KEY=sk-xxx
```

> 国内模型推荐：通义千问（qwen-turbo/qwen-plus）、DeepSeek（deepseek-chat）。
> 切换模型只需改环境变量，无需改代码。

---

### 6.1 IntentParser

**用途**：解析用户自然语言输入，提取结构化出行意图，在意图理解节点调用。

**System Prompt：**

```
你是一个机票查询助手，专注于从用户输入中提取出行意图。

## 任务
从用户输入中提取：origin（出发城市）、destination（目的地）、date_range（出行日期）、budget（预算，未提及则为null）、constraints（约束列表，无则为空数组）。

## 判断逻辑
逐一检查必填字段：
1. origin：是否提到出发城市？"回成都"="成都"，未提及则为null
2. destination：是否有明确目的地？"回家"需结合上下文，无法判断则为null
3. date_range：时间表述转换为具体日期。"五一"=2026-05-01~05-05，"下周末"=最近的周六周日，"清明"=2026-04-04~04-06

## 约束识别
- "不要太早"/"不要红眼" → constraints: ["avoid_redeye"]
- "直飞" → constraints: ["direct_only"]
- "尽量早点到" → constraints: ["prefer_morning"]

## 输出格式
纯JSON，不加代码块，不加解释：
{"origin":"北京","destination":"三亚","date_range":{"start":"2026-05-01","end":"2026-05-05"},"budget":600,"constraints":["avoid_redeye"]}

不确定的字段填null，不要编造。

## 限制
- 城市名用中文，不要转为机场三字码
- 日期统一YYYY-MM-DD格式
- 只输出JSON，没有多余文字
```

**输入 Message 构成：**

| role | 内容 |
|------|------|
| system | 上述 System Prompt |
| user | 用户当前输入文本 |

**输出格式（真实示例）：**

```json
{"origin":"北京","destination":"三亚","date_range":{"start":"2026-05-01","end":"2026-05-05"},"budget":600,"constraints":["avoid_redeye"]}
```

**解析方式：**

```python
import json, re

def parse_intent(llm_output: str):
    try:
        return json.loads(llm_output.strip())
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', llm_output, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except:
                pass
        # 解析失败，触发降级
        return {"origin": None, "destination": None, "date_range": None,
                "budget": None, "constraints": [], "_parse_failed": True}
```

**边界处理：**
- 解析失败（`_parse_failed=True`）→ fallback_triggered=true，展示兜底提示
- 输出为空 → 同上，不重试
- 相对日期（"下周"）→ 模型推算，以运行时当日为基准

---

### 6.2 PreferenceMatch

**用途**：基于用户偏好记忆，判断每条航班与偏好的匹配情况，在偏好匹配节点调用。

**实现方式：纯工程规则（无 LLM 调用）**

逻辑明确、可枚举，改为代码直接计算，节省 token 和延迟。

**Python 伪代码：**

```python
def match_preferences(flight: dict, user_memory: dict) -> dict:
    reasons = []
    boost = False

    # 1. 心理价位
    if user_memory.get("budget") and flight["lowest_price"] <= user_memory["budget"]:
        reasons.append("在你的心理价位以内")

    # 2. 偏好航司
    if flight["airline"] in user_memory.get("preferred_airlines", []):
        reasons.append(f"你常飞的{flight['airline']}")

    # 3. 出行习惯（avoid_redeye）
    if "avoid_redeye" in user_memory.get("constraints", []):
        dep_hour = int(flight["dep_time"].split(":")[0])
        if dep_hour >= 6:
            reasons.append("符合你的出行习惯")

    # 4. 常去城市（boost）
    if flight["destination"] in user_memory.get("frequent_cities", []):
        boost = True  # 不输出 reason，仅影响排序

    matched = len(reasons) > 0
    return {
        "flight_no": flight["flight_no"],
        "matched": matched,
        "boost": boost,
        "reasons": reasons[:3]  # 最多3条
    }
```

**输出结构（与原 LLM 输出格式一致）：**

```json
[
  {"flight_no": "HU7833", "matched": true, "boost": false, "reasons": ["在你的心理价位以内", "你常飞的海南航空"]},
  {"flight_no": "CZ6901", "matched": false, "boost": false, "reasons": []}
]
```

**原 LLM Prompt（已废弃，保留供参考）：**

<details>
<summary>展开查看原 LLM Prompt</summary>

```
你是用户偏好分析助手。

## 任务
根据用户偏好数据和航班列表，判断每条航班是否与用户偏好匹配，并输出匹配原因。

## 判断逻辑（逐条检查）
1. 价格：lowest_price ≤ user.budget → 匹配，原因"在你的心理价位以内"
2. 航司：airline in user.preferred_airlines → 匹配，原因"你常飞的[航司名]"
3. 时间：user有avoid_redeye且dep_time≥06:00 → 匹配，原因"符合你的出行习惯"
4. 目的地常去城市：destination in user.frequent_cities → 不输出原因，在结果中用boost字段标记

## 输出格式
JSON数组，每条航班对应一个对象：
[{"flight_no":"HU7833","matched":true,"boost":false,"reasons":["在你的心理价位以内","你常飞的海南航空"]}]

matched=true：至少满足一条偏好维度
reasons：直接用于前端展示，每条≤15字，最多3条
boost：目的地为常去城市时为true，影响排序权重

## 限制
- 用户偏好为空时，输出空数组[]
- 不要输出与偏好无关的分析
- reasons文案必须是用户能读懂的话，不是字段名
```

</details>

---

### 6.3 ValueJudge

**用途**：综合价格、历史均价、偏好匹配，输出值得买信号和一句话建议，在判断节点调用。

**System Prompt：**

```
你是机票价值判断助手，帮用户判断当前机票是否值得买。

## 任务
对每张票，输出触发的值得买信号列表和一句话购买建议。

## 判断逻辑（先推理再输出结论）
对每张票依次判断：
1. lowest_price 与 history_avg_90d 的差值百分比，差值 > 15% 触发"历史低价"信号
2. 是否在用户心理价位内（由 preference_matched 字段传入）
3. 出行日期是否为节假日（由 is_holiday 字段传入）
4. 综合以上，生成不超过20字的一句话建议：先告诉用户买/不买/观望，再给最关键的一条理由

## 输出格式
JSON数组：
[{"flight_no":"HU7833","signals":["历史低价","符合心理价位"],"advice":"建议现在买，比均价低43%且在预算内"}]

## 限制
- advice 不超过20字
- 历史数据不足时，signals为[]，advice输出"数据有限，仅供参考"
- 不捏造数据，只用传入数据做判断
- is_holiday=true 时可在 advice 文案中提及节假日，但不得将"节假日稀缺"写入 signals 数组
- 只输出JSON，不加解释
```

**is_holiday 计算规则（后端工程计算，非 LLM）：**

```python
HOLIDAY_RANGES = [
    ("2026-01-01", "2026-01-01"),  # 元旦
    ("2026-02-17", "2026-02-23"),  # 春节
    ("2026-04-04", "2026-04-06"),  # 清明
    ("2026-05-01", "2026-05-05"),  # 五一
    ("2026-06-19", "2026-06-21"),  # 端午
    ("2026-10-01", "2026-10-07"),  # 国庆/中秋
]

def is_holiday(date_str: str) -> bool:
    from datetime import date
    d = date.fromisoformat(date_str)
    for start, end in HOLIDAY_RANGES:
        if date.fromisoformat(start) <= d <= date.fromisoformat(end):
            return True
    return False
```

> 节假日列表每年人工维护一次，不需要外部 API。

**输入 Message 构成：**

| role | 内容 |
|------|------|
| system | 上述 System Prompt |
| user | 航班列表（含lowest_price/history_avg_90d/is_holiday）+ preference_matched结果 |

**输出格式（真实示例）：**

```json
[
  {
    "flight_no": "HU7833",
    "signals": ["历史低价", "符合心理价位"],
    "advice": "建议现在买，比均价低43%且在预算内"
  },
  {
    "flight_no": "CZ6901",
    "signals": [],
    "advice": "价格正常，可继续关注"
  }
]
```

---

## 7. 数据结构定义

本节定义前后端之间的完整数据契约，以前端 `lib/api.ts` 中的 TypeScript 类型为准。

### 7.1 核心 DTO：DealCardDto（航班结果卡片）

前端 `DiscoveryCardContent` 组件依赖该结构渲染航班卡片，字段缺失会导致展示异常。

| 字段 | 类型 | 必填 | 前端用途 |
|------|------|------|---------|
| id | string | 是 | 列表 key |
| system_id | string | 是 | 内部标识 |
| platform | string | 是 | 「AI建议在 {platform} 下单」文案 |
| origin_city | string | 是 | 出发地展示 |
| origin_code | string | 是 | IATA 三字码 |
| destination_city | string | 是 | 目的地展示 |
| destination_code | string | 是 | IATA 三字码，用于 picsum 图片 seed |
| depart_date | string | 是 | 日期标签（YYYY-MM-DD） |
| airline | string | 是 | 航司名 |
| depart_time | string | 是 | 出发时间（HH:mm） |
| arrive_time | string | 是 | 到达时间（HH:mm） |
| price | number | 是 | 裸票价（¥），票价区显示 |
| tax | number | 是 | 机建燃油税（¥），总价计算 |
| baggage_fee | number | 是 | 行李额费用（¥），0 = 免费 |
| has_baggage | boolean | 是 | 控制行李图标颜色与文案 |
| recommend_score | string | 否 | 「发现指数」0-10 分，后端计算，见计算规则 |
| prices | PriceItem[] | 是 | 各平台价格列表，含 lowest 标记 |
| original_price | number | 否 | 原价（划线价，暂未渲染） |
| discount_rate | number | 否 | 折扣率（暂未渲染） |
| cabin | string | 否 | 舱位（暂未渲染） |
| signals | string[] | 是 | 值得买信号标签，如 ["历史低价"] |
| confidence | 'high'\|'medium'\|'low' | 是 | 置信度（暂未渲染，预留）|
| verdict | string | 是 | 一句话判断，如「建议现在买，比均价低43%」|
| booking_url | string | 否 | 预订跳转深链（APP Deep Link），格式见下方说明 |
| h5_fallback_url | string | 否 | APP 未安装时降级用的 H5 页面链接，与 booking_url 配套；Mock 阶段填对应平台 H5 搜索页 URL |

**PriceItem 子结构：**

```typescript
{ name: string; price: number; lowest?: boolean }
```

前端按 `lowest=true` 高亮最低价，其他平台价格显示为 45% 透明度。

**booking_url 深链规则（MVP）：**

| 平台 | Deep Link 格式 | 示例 |
|------|---------------|------|
| 携程 | `ctrip://flight/search?from={origin_code}&to={dest_code}&date={depart_date}` | `ctrip://flight/search?from=BJS&to=SYX&date=2026-05-01` |
| 去哪儿 | `qunar://flight?from={origin_code}&to={dest_code}&date={depart_date}` | `qunar://flight?from=BJS&to=SYX&date=2026-05-01` |
| 飞猪 | `alitrip://flight?from={origin_code}&to={dest_code}&date={depart_date}` | `alitrip://flight?from=BJS&to=SYX&date=2026-05-01` |

> APP 未安装时降级行为：前端判断 `window.location.href = deep_link` 后 1.5s 无响应，自动 fallback 到对应平台 H5 页面（`h5_fallback_url` 字段）。Mock 阶段 booking_url 可填示例值，前端点击直接跳转。

**总价计算规则（前端执行）：**

```
综合总价 = price + tax + baggage_fee
```

**recommend_score 计算规则（后端执行，0-10 分）：**

```
历史低价原始分 = max(0, 1 - lowest_price / history_avg_90d)   # 0~1
偏好匹配原始分 = min(matched_count, 3) / 3                     # 0~1
加成原始分     = (stops==0 ? 1 : 0) × 0.5 + (baggage_fee==0 ? 1 : 0) × 0.5  # 0~1

recommend_score = (历史低价原始分 × 0.5 + 偏好匹配原始分 × 0.3 + 加成原始分 × 0.2) × 10
```

结果四舍五入保留一位小数，以字符串形式输出（如 `"9.5"`）。历史数据不足时，历史低价得分按 0 计算。

**deals 排序规则（后端执行）：**

1. 主排序：综合总价（`price + tax + baggage_fee`）升序
2. 次排序：`boost=true`（目的地为用户常去城市）的航班同等价位优先
3. 第三排序：`recommend_score` 降序

`deals[0]` 即为综合最优航班，前端直接展示为结果卡片。

**完整示例：**

```json
{
  "id": "deal-001",
  "system_id": "HU7833-20260501",
  "platform": "携程",
  "origin_city": "北京",
  "origin_code": "BJS",
  "destination_city": "三亚",
  "destination_code": "SYX",
  "depart_date": "2026-05-01",
  "airline": "海南航空",
  "depart_time": "09:30",
  "arrive_time": "14:20",
  "price": 389,
  "tax": 60,
  "baggage_fee": 0,
  "has_baggage": true,
  "recommend_score": "9.5",
  "prices": [
    {"name": "携程", "price": 389, "lowest": true},
    {"name": "去哪儿", "price": 399},
    {"name": "飞猪", "price": 410}
  ],
  "signals": ["历史低价", "符合心理价位"],
  "confidence": "high",
  "verdict": "建议现在买，比均价低43%且在预算内",
  "booking_url": "ctrip://flight/search?from=BJS&to=SYX&date=2026-05-01",
  "h5_fallback_url": "https://flights.ctrip.com/online/list/oneway-bjs-syx?depdate=2026-05-01"
}
```

### 7.2 POST /api/search 完整响应：SearchResponseDto

```typescript
{
  user_id: string
  query: {
    raw_text: string          // 用户原始输入
    normalized_text: string   // 标准化后的意图摘要
    origin_city: string
    origin_code: string
    destination_city: string
    destination_code: string
    date_start: string        // YYYY-MM-DD
    date_end: string
    budget?: number
  }
  deals: DealCardDto[]        // 航班结果列表，前端取 deals[0] 展示卡片
  analysis: {
    min_price?: number
    max_price?: number
    avg_price?: number
    avg_90d?: number          // 近90天均价
    lower_than_avg?: number   // 比均价低的百分比
    price_spread_pct?: number // 平台间价差百分比
    match_score: number       // 偏好匹配分（0-1）
    within_budget: boolean
    matched_preferences: string[]
  }
  recommendation: {
    action: 'buy_now' | 'watch' | 'skip'
    text: string              // 前端展示的 AI 建议文案
    confidence: 'high' | 'medium' | 'low'
    signals: string[]
  }
  meta: {
    generated_at: string      // ISO 8601
    source?: string
    request_id?: string
    result_count?: number
    fallback_mode?: boolean
  }
}
```

**前端使用逻辑：**

- `recommendation.text` 作为 assistant 消息气泡的内容
- `deals[0]` 作为卡片展示（取最优航班）
- `deals.length` 用于「为您找到 N 个航班」文案
- `meta.fallback_mode=true` 时前端提示「暂无数据」

### 7.3 GET /api/memory 完整响应：MemoryResponseDto

```typescript
{
  user_id: string
  memories: {
    id: string
    field: string             // 字段标识，如 "budget", "frequent_cities"
    label: string             // 用户可读标签，如「心理价位」
    value: string | number | string[]
    value_display: string     // 格式化展示值，如「¥600以内」
    source: 'manual' | 'auto' // 手动设置 or 自动学习
    updated_at: string
  }[]
  query_history: {
    query: { text?: string; [key: string]: unknown }
    created_at: string
  }[]
  click_history: {
    flight_info: { [key: string]: unknown }
    created_at: string
  }[]
  meta: ApiMeta
}
```

**前端使用逻辑（MemoryPage）：**

- `memories` → 渲染「出行偏好」章节的 timeline 和 priorities
- `query_history` → 渲染「出行历史」章节，显示最近 3 条查询
- 若后端返回失败，静默降级为静态示例数据

### 7.4 GET /api/recommendations 完整响应：RecommendationsResponseDto

```typescript
{
  user_id: string
  cards: {
    id: string
    title: string             // 卡片标题
    reason: string            // 推荐理由，如「近期有你常看的路线特价」
    query_hint: string        // 点击可填入输入框的示例问句
    tags: string[]            // 标签，如 ["直飞", "含行李"]
    preview_deal?: DealCardDto // 探索页卡片展示用
  }[]
  meta: ApiMeta
}
```

**前端使用逻辑：**

- ChatPage：取 `cards[*].query_hint` 最多 4 条，显示为输入框下方的快捷问题标签
- ExplorePage：取有 `preview_deal` 的 cards，渲染瀑布流卡片；`destination_code` 作为图片 seed

---

## 8. 后端 API 接口规范

### 8.1 接口总览

| 方法 | 路径 | 功能 | 调用页面 |
|------|------|------|---------|
| POST | /api/session | 创建新会话，获取 session_id | ChatPage（开始新对话时）|
| POST | /api/search | 自然语言查票（主链路） | ChatPage |
| GET | /api/memory | 获取用户记忆 | MemoryPage |
| PATCH | /api/memory | 更新单个记忆字段 | MemoryPage（手动编辑）|
| DELETE | /api/memory/{field} | 删除单个记忆字段 | MemoryPage（删除条目）|
| GET | /api/recommendations | 获取个性化推荐卡片 | ChatPage、ExplorePage |
| POST | /api/alerts | 创建价格监控 | ChatPage（卡片按钮）|
| GET | /api/alerts | 获取监控列表 | PersonalPage |

### 8.2 POST /api/search

**请求：**

```json
{
  "user_id": "xxx",
  "session_id": "yyy",
  "message": "五一去三亚，预算600，不要红眼航班"
}
```

**处理链路（后端执行）：**

1. 根据 session_id 加载对话历史（无 session 时自动创建）
2. 调用 IntentParser Prompt，将对话历史作为上下文传入 → 解析结构化意图
3. 若意图不完整（缺 origin/destination/date_range）→ 返回追问响应（见 8.2.1）
4. 意图完整 → 并行执行：
   - 查价（mock 数据 or 真实 API）
   - 偏好匹配（读取 user memory，若 memories 为空则跳过）
5. 按排序规则对 deals 排序（见 7.1 deals 排序规则）
6. 调用 ValueJudge Prompt → 生成 signals、verdict、recommend_score
7. 组装 SearchResponseDto 返回；异步写入 query_history

**正常响应**：见 7.2 节结构。

**8.2.1 追问响应（意图不完整时）：**

```json
{
  "user_id": "demo-user",
  "query": null,
  "deals": [],
  "analysis": {"match_score": 0, "within_budget": false, "matched_preferences": []},
  "recommendation": {
    "action": "watch",
    "text": "请问您从哪个城市出发？",
    "confidence": "low",
    "signals": []
  },
  "meta": {
    "generated_at": "2026-04-18T10:00:00Z",
    "fallback_mode": false,
    "clarify_count": 1
  }
}
```

追问时 `deals=[]`，前端仅展示 `recommendation.text` 文本气泡，不展示卡片。

**错误响应（HTTP 200，fallback）：**

```json
{
  "deals": [],
  "recommendation": {"action": "skip", "text": "没听明白，换个说法试试？", ...},
  "meta": {"fallback_mode": true}
}
```

### 8.3 GET /api/memory

**请求参数：** `?user_id=demo-user`

**响应：** 见 7.3 节结构。

**memory field 枚举（后端需支持）：**

| field | label | value 类型 | 示例 |
|-------|-------|-----------|------|
| budget | 心理价位 | number | 600 |
| frequent_cities | 常去城市 | string[] | ["成都", "三亚"] |
| preferred_airlines | 偏好航司 | string[] | ["海南航空"] |
| constraints | 出行习惯 | string[] | ["avoid_redeye"] |
| travel_scenes | 出行场景 | string[] | ["holiday_home"] |

### 8.4 PATCH /api/memory

**请求：**

```json
{
  "user_id": "demo-user",
  "field": "budget",
  "value": 800,
  "source": "manual"
}
```

**响应：** 同 GET /api/memory，返回更新后的完整 MemoryResponseDto。

### 8.5 DELETE /api/memory/{field}

**请求参数：** `?user_id=demo-user`，路径参数 `field` 为要删除的字段名。

**响应：** 同 GET /api/memory，返回删除后的完整 MemoryResponseDto。

### 8.6 GET /api/recommendations

**请求参数：** `?user_id=demo-user`

**响应：** 见 7.4 节结构。

**生成规则：**

- 用户 memories 不为空 → 基于偏好（frequent_cities、budget 等）生成个性化推荐
- 冷启动（memories 为空）→ 返回固定热门路线卡片（北京↔三亚、北京↔成都、上海↔三亚、成都↔丽江、广州↔青岛等）
- 每次调用至少返回 4 张卡片，最多 8 张
- 每张卡片必须包含 `preview_deal`（ExplorePage 需要），`query_hint`（ChatPage 需要）
- Mock 数据需覆盖上述所有出发地（不能只有北京出发）

---

## 9. 前端页面与接口需求

### 9.1 页面总览

| 页面 | 路由 | 依赖接口 | 核心功能 |
|------|------|---------|---------|
| ChatPage（对话空间） | / | POST /api/session, POST /api/search, GET /api/recommendations, POST /api/alerts | 主查票对话流 |
| ExplorePage（探索发现） | /explore | GET /api/recommendations | 瀑布流推荐 + 盲盒 |
| MemoryPage（记忆空间） | /memory | GET /api/memory, PATCH /api/memory, DELETE /api/memory/{field} | 日记式记忆展示 |
| PersonalPage（个人中心） | /personal | — （MVP 纯静态，GET /api/alerts 在 v1.1 接入）| 关系图 + 监控列表（静态示例）|

### 9.2 ChatPage 数据流

```
用户输入 → POST /api/search
  → deals[0] → DiscoveryCardContent 卡片
  → recommendation.text → assistant 气泡文案
  → deals.length → 「找到 N 个航班」兜底文案

页面初始化 → GET /api/recommendations
  → cards[*].query_hint (max 4) → 快捷问题标签
```

**卡片字段映射（dealToCardProps）：**

| DealCardDto 字段 | DiscoveryCardContent prop |
|-----------------|--------------------------|
| origin_city | from |
| destination_city | to |
| depart_date | date |
| price | basePrice |
| tax | tax |
| baggage_fee | baggageFee |
| has_baggage | hasBaggage |
| platform | platform |
| recommend_score | recommendScore |
| prices | prices |

### 9.3 ExplorePage 数据流

```
页面初始化 → GET /api/recommendations
  → cards（过滤 preview_deal 不为空的）
  → 每张卡片：
      preview_deal.origin_city → from
      preview_deal.destination_city → to
      preview_deal.price → 展示价格
      preview_deal.depart_date → 日期
      card.reason → 推荐理由文案
      destination_code → picsum 图片 seed

盲盒按钮 → 随机取 visibleDeals 中一张 → 弹出 DiscoveryCardContent 详情
```

**盲盒筛选逻辑：**
- 有出发地输入时：`cards.filter(c => c.preview_deal?.origin_city.includes(departure))`
- 无筛选：取全部 cards（有 preview_deal 的）随机

### 9.4 MemoryPage 数据流

```
页面初始化 → GET /api/memory
  → memories → 覆盖「出行偏好」章节的 timeline 和 priorities
      每条 memory → { time: i+1, title: label, detail: `当前记录：value_display（来源：source）` }
  → query_history → 覆盖「出行历史」章节
      取前3条 → { time: i+1, title: query.text, detail: `搜索于 ${date}` }

后端失败 → 静默，保留 4 个静态章节（偏好/习惯/想法/历史）
```

**记忆章节 ID 对应关系：**

| chapter.id | 数据来源 | 更新字段 |
|-----------|---------|---------|
| preference | memories | timeline, priorities, coverNote |
| history | query_history | timeline, priorities, coverNote, leftMeta |
| habit | 静态（暂无 API） | — |
| idea | 静态（暂无 API） | — |

### 9.5 PersonalPage（当前状态）

当前为纯静态页面，无 API 调用。图中节点和通知设置均为硬编码示例数据。

**待接入（v1.1）：**
- `价格监控` 节点需要接 GET /api/alerts（未实现）
- `对话历史` 节点来自 GET /api/memory 的 query_history
- 通知设置 toggle 需要 PATCH /api/settings（未实现）

---

## 10. 埋点

| 事件名 | 触发时机 | 关键参数 |
|--------|---------|---------|
| search_submitted | 用户提交查询 | query_text, user_id, clarify_count |
| intent_parsed | 意图解析完成 | intent_complete, parse_failed |
| result_viewed | 结果页展示 | result_count, has_signals, has_preference |
| ticket_clicked | 用户点击某张票 | flight_no, platform, price, signals |
| purchase_jumped | 跳转购买链接 | flight_no, platform, price |
| memory_edited | 个人中心修改偏好 | field_name |
| memory_cleared | 用户清空所有记忆 | — |
| fallback_triggered | 降级触发 | reason（parse_failed / clarify_exceeded / timeout） |

---

## 11. 性能与质量指标

| 指标项 | 目标值 | 备注 |
|--------|--------|------|
| 意图解析成功率 | > 90% | parse_failed率 < 10% |
| 查询到结果展示 P95 | < 3s | 判断建议可异步追加，不阻塞价格展示 |
| 判断建议生成 P95 | < 3s | 异步渲染，先展示价格后补充建议 |
| 前端首屏加载 | < 1.5s | — |
| /api/recommendations 响应 | < 500ms | ChatPage 初始化时调用，影响首屏体验 |
| /api/memory 响应 | < 300ms | MemoryPage 进入时调用 |

---

## 12. MVP范围界定

### MVP 包含（后端必须实现）

- `POST /api/session`：创建 session，返回 session_id
- `POST /api/search`：意图解析（含多轮上下文）+ Mock查价 + 偏好匹配 + 值得买判断 + deals 排序，返回 SearchResponseDto
- `GET /api/recommendations`：冷启动返回固定热门卡片；memories 不为空后返回个性化推荐，必须含 preview_deal
- `GET /api/memory`：返回用户偏好 memories + query_history（MemoryPage 日记需要）
- `PATCH /api/memory`：手动编辑偏好字段
- `DELETE /api/memory/{field}`：删除单条偏好
- `POST /api/alerts`：创建价格监控记录（存储意图，MVP 不做推送）
- `GET /api/alerts`：获取用户监控列表
- 后端分配匿名 user_id（首次 API 请求时生成并下发）
- 值得买信号（历史低价、符合心理价位、符合出行习惯）
- AI 一句话购买建议（≤20字，写入 recommendation.text 和 verdict）
- recommend_score 按规则计算（见 7.1）
- 偏好自动学习：每次 search 后异步写入 query_history

### MVP 不包含（明确排除）

- 真实API数据接入（Mock代替）
- 用户账号注册/登录（本地存储）
- 退改签规则解析
- 价格历史图表
- 航班动态/延误提醒
- 限时特卖信号（需接入航司促销数据）
- App（纯Web）

---

## 13. 版本规划

| 版本号 | 核心内容 | 上线时间 |
|--------|---------|---------|
| v1.0 MVP | 对话查票 + Mock数据 + 值得买信号 + 后端偏好记忆（PostgreSQL） | [待填] |
| v1.1 | 偏好自动学习 + 个性化推荐卡片 | [待填] |
| v2.0 | 真实API接入 + 账号体系 + 价格历史图表 | [待填] |

---

## 待确认清单

**已确认：**
- [x] 记忆存储：纯后端 PostgreSQL，前端不用 localStorage 存偏好
- [x] user_id：后端首次 API 响应时分配匿名 ID，前端存 localStorage
- [x] 多轮对话：后端维护 session，前端传 session_id
- [x] 监控价格：MVP 包含基础版（存储意图，不做推送）
- [x] deals 排序：综合总价最低优先，boost 同等价位优先
- [x] recommend_score：后端规则计算，见 7.1
- [x] 新用户偏好阈值：按 memories 是否为空判断，不依赖 query_count

**待确认（已全部确认）：**

- [x] **跳转购买方式**：深链到平台 APP，APP 未安装降级到 H5，见 7.1 booking_url 深链规则
- [x] **节假日信号**：保留，后端写死节假日日期列表（工程规则），见 6.3 is_holiday 计算规则
- [x] **历史均价 Mock 数据**：`history_avg_90d = lowest_price × random(1.2, 1.5)`，随机浮动模拟历史高于当前
- [x] **追问降级表单**：Modal 浮层弹出（不跳页），见 5.2 追问逻辑第4条
- [x] **Prompt 模型选型**：环境变量配置（`MODEL_INTENT` / `MODEL_JUDGE`），支持国内模型（通义/DeepSeek等），见 6 章 Prompt 汇总
- [x] **PreferenceMatch 改为纯工程规则**：已改为 Python 规则代码，见 6.2
