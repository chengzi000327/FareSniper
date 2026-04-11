# 特价机票发现平台 - 前端技术方案

## 1. 目标与定位

前端负责把产品故事和用户价值完整呈现出来，并且在后端尚未完成时也能独立推进。

前端的核心职责不是承载业务逻辑，而是：
- 承担产品交互入口与结果展示
- 承担“记忆显性化”的可视化表达
- 为后端 API、SSE、错误态、加载态预留稳定接入层
- 在阶段一用 mock 独立交付，在阶段二/三平滑切换到真实后端

这意味着前端必须坚持“纯 UI + 轻状态 + 强契约”的边界，不在浏览器里做航班计算、价格判断、偏好推理。

## 2. 分阶段实现策略

### 阶段一：纯前端 MVP

目标：1 天内交付一个可分享、可点击、可讲故事的演示版本。

范围：
- 首页
- 结果页
- 个人中心
- 本地 mock 数据
- localStorage 偏好编辑

明确不做：
- 不接后端
- 不接 LLM
- 不做鉴权
- 不做复杂状态管理

前端在这一阶段的关键是先把信息架构和用户心智跑通，而不是提前做重后端依赖。

### 阶段二：接入真实后端

目标：保留阶段一 UI，不推翻页面结构，只替换数据来源。

范围：
- 把 mock 查询切到真实 `/api/search`
- 把个人偏好切到 `/api/memory`
- 把首页推荐切到 `/api/recommendations`
- 补齐 loading、empty、error、retry

阶段二不应该大改页面，只做“数据接线”和“状态严谨化”。

### 阶段三：体验精细化

目标：让前端能承接 Agent 架构的复杂输出，但仍保持界面简单。

范围：
- SSE 流式展示 AI 建议
- 更细的推荐标签和解释区块
- 记忆可视化增强
- 错误降级和多状态反馈

## 3. 技术选型

- 框架：Next.js 14 App Router
- 语言：TypeScript
- 样式：Tailwind CSS
- 组件：shadcn/ui
- 状态管理：React Context + 局部 useState
- 服务端通信：`fetch`
- 流式通信：SSE
- 数据缓存：SWR
- 本地持久化：`localStorage`
- 部署：Vercel

选择原则：
- 不引入 Redux、Zustand 这类额外状态库，避免阶段一过度设计
- 不把业务判断写进前端，前端只消费后端结构化结果
- 尽量通过统一 `api-client` 层隔离后端变化

## 4. 页面与模块设计

### 4.1 首页 `/`

职责：
- 承接自然语言输入
- 展示热门低价卡片
- 展示个性化推荐卡片
- 提供进入结果页的主入口

模块建议：
- `ChatInput`
- `HotDealsCard`
- `PersonalizedCard`
- `SearchSuggestions`

交互流程：
- 用户输入自然语言
- 阶段一：前端关键词匹配后跳转结果页
- 阶段二/三：调用搜索接口，再跳转或原地展示加载过程

### 4.2 结果页 `/results`

职责：
- 展示航班搜索结果
- 展示 AI 推荐结论
- 展示价格/心理价/值得买信号
- 展示空态、失败态、重试入口

模块建议：
- `FlightResultCard`
- `AIRecommendationPanel`
- `SignalTagList`
- `SearchSummaryBar`
- `ResultsSkeleton`

展示原则：
- 卡片上优先展示“用户最关心”的字段：价格、日期、航司、起降时间、推荐信号
- 把 AI 文案与结构化指标分开展示，避免用户觉得是“纯模型瞎说”

### 4.3 个人中心 `/profile`

职责：
- 展示用户长期偏好
- 支持编辑、删除、确认保存
- 显性化展示“系统记住了什么”

模块建议：
- `PreferenceList`
- `PreferenceItem`
- `PreferenceEditorDialog`
- `PreferenceEmptyState`

数据原则：
- 阶段一：读写 localStorage
- 阶段二：与后端 memory API 同步
- 阶段三：增加来源字段，如手动设置/系统归纳

## 5. 推荐目录结构

```txt
frontend/
├── app/
│   ├── page.tsx
│   ├── results/page.tsx
│   ├── profile/page.tsx
│   └── layout.tsx
├── components/
│   ├── ChatInput.tsx
│   ├── HotDealsCard.tsx
│   ├── PersonalizedCard.tsx
│   ├── FlightResultCard.tsx
│   ├── AIRecommendationPanel.tsx
│   ├── SignalTagList.tsx
│   └── PreferenceItem.tsx
├── lib/
│   ├── api-client.ts
│   ├── sse.ts
│   ├── storage.ts
│   └── constants.ts
├── hooks/
│   ├── usePreferences.ts
│   ├── useRecommendations.ts
│   └── useFlightSearch.ts
├── mocks/
│   ├── flights.json
│   ├── preferences.json
│   └── hot-deals.json
├── types/
│   ├── flight.ts
│   ├── memory.ts
│   └── api.ts
└── providers/
    └── app-provider.tsx
```

## 6. 前端数据模型建议

建议前端统一维护以下类型，避免 mock 和真实接口切换时反复改组件。

```ts
export type FlightResult = {
  id: string;
  platform: string;
  origin: string;
  destination: string;
  departDate: string;
  airline: string;
  departTime: string;
  arriveTime: string;
  price: number;
  cabin?: string;
  signals?: string[];
};

export type Recommendation = {
  recommendation: string;
  signals: string[];
  confidence: "high" | "medium" | "low";
};

export type PreferenceItem = {
  field: string;
  label: string;
  value: string | number | string[];
  source?: "manual" | "auto";
  updatedAt?: string;
};
```

## 7. API 对接方案

前端统一通过 `lib/api-client.ts` 调后端，不允许组件直接写 URL。

### 7.1 搜索接口

建议：
- `POST /api/search`

请求：
```json
{
  "user_id": "u1",
  "message": "五一去三亚，600以内"
}
```

响应：
```json
{
  "query": {
    "origin": "BJS",
    "destination": "SYX",
    "date_start": "2026-05-01",
    "date_end": "2026-05-03",
    "budget": 600
  },
  "flights": [],
  "recommendation": {
    "recommendation": "建议现在买",
    "signals": ["近90天低位", "符合心理价位"],
    "confidence": "high"
  }
}
```

### 7.2 记忆接口

建议：
- `GET /api/memory?user_id=u1`
- `PATCH /api/memory`

PATCH 请求：
```json
{
  "user_id": "u1",
  "field": "price_anchor",
  "value": 600,
  "source": "manual"
}
```

### 7.3 推荐接口

建议：
- `GET /api/recommendations?user_id=u1`

用途：
- 首页个性化卡片
- 热门低价入口

## 8. SSE 流式方案

阶段三建议新增：
- `POST /api/chat`

前端职责：
- 建立 SSE 连接
- 逐段接收 AI 推荐文本
- 将最终结构化结果落盘到页面状态

推荐事件类型：
- `status`
- `partial_recommendation`
- `final_result`
- `error`

前端表现：
- 有流式文本时显示“AI 正在判断是否值得买”
- 如果 SSE 中断，保底切回普通结果请求或展示失败提示

## 9. 状态管理策略

建议按“页面状态”和“全局轻状态”拆分。

全局状态：
- 当前用户 ID
- 偏好缓存
- API 地址配置

页面级状态：
- 当前查询文案
- 搜索结果列表
- 推荐文案
- loading/error/empty

约束：
- 偏好用 Context 即可
- 结果页请求状态用 SWR 或局部 state 即可
- 不做前端复杂事件总线

## 10. Mock 到真实 API 的切换策略

为了让前端同学能先独立推进，建议在 `api-client` 内做一层开关：

- `mock mode`：返回 `mocks/*.json`
- `api mode`：请求真实后端

建议环境变量：
- `NEXT_PUBLIC_API_MODE=mock|remote`
- `NEXT_PUBLIC_API_URL=http://localhost:8000`

这样阶段一可以不等待后端，阶段二切换也只改一层。

## 11. 视觉与交互原则

这类产品不是传统 OTA 搜索页，更像“AI 帮你发现值不值得买”，所以视觉上要强调判断感，而不是密集表格感。

建议：
- 首页重点放在对话入口和推荐卡片，不要一上来就做复杂筛选器
- 结果页的“AI 建议”应该固定在首屏可见区域
- 值得买信号用短标签表达，不要把解释都藏在长段落里
- 个人中心要强调“被记住”的体验，比如来源、更新时间、可编辑性

## 12. 与后端协作边界

前端负责：
- 页面、组件、状态、交互、错误展示
- API 请求封装
- mock 数据和联调页面

前端不负责：
- 意图解析
- 航班排序和价格判断
- 偏好推理
- 任何 AI 决策逻辑

前端需要后端保证：
- 接口字段稳定
- 推荐结果结构化返回
- 错误码和错误文案可识别
- SSE 事件格式固定

## 13. 前端开发顺序建议

1. 先搭骨架：初始化 Next.js、Tailwind、shadcn/ui。
2. 再做三页静态结构：首页、结果页、个人中心。
3. 再接 mock 数据，让页面先可点击。
4. 再封装 `api-client`，为真实后端预留切换层。
5. 最后补 loading、empty、error 和移动端适配。

## 14. 主要风险与建议

- 风险：阶段一页面直接写死逻辑，阶段二切接口时会返工。
  建议：从第一天开始统一走 `types/` 和 `api-client`。

- 风险：结果页 UI 过度依赖真实字段，后端未完成时难推进。
  建议：先定义稳定的最小字段集，mock 按最终接口形状构造。

- 风险：SSE 接入过早，影响 MVP 速度。
  建议：阶段一/二先用普通请求，阶段三再加流式。

## 15. 最终交付标准

前端方案完成后，应该达到以下标准：
- 前端同学可以不等待后端先完成阶段一
- 阶段二只改数据接线，不推翻页面结构
- 阶段三能承接 SSE 和复杂推荐结果
- 全程维持“前端纯 UI，后端承载业务”的边界
