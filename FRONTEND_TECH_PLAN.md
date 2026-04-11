# 特价机票发现平台 — 前端技术方案（最终版）

## 1. 定位与边界

前端的职责：**纯 UI + 轻状态 + 强契约**。

- 承担产品交互入口与结果展示
- 承担"记忆显性化"的可视化表达
- 通过统一 `api-client` 层接入后端，不在组件内直接写 URL 或业务逻辑
- 不做意图解析、价格判断、偏好推理——这些全是后端的事

---

## 2. 技术选型

| 层 | 选型 | 理由 |
|---|---|---|
| 框架 | Next.js 14 App Router | 文件路由、SSR 预留、Vercel 一键部署 |
| 语言 | TypeScript | 类型即契约，mock 到真实接口切换零改组件 |
| 样式 | Tailwind CSS | 设计 token 统一管理，无冗余 CSS |
| 组件 | shadcn/ui（按需引入） | 无样式侵入，只取 Primitive 层 |
| 字体 | Spectral（展示）+ DM Sans（正文）+ JetBrains Mono（系统标签）| 编辑质感，区别于通用 OTA |
| 状态 | React Context + 局部 useState | 无多余状态库 |
| 请求 | `lib/api-client.ts` 统一封装 fetch | 支持 mock/remote 一键切换 |
| 流式 | SSE via `lib/sse.ts` | 承接 AI 流式推荐 |
| 持久化 | localStorage（偏好缓存） | 离线可用，后端同步时自动合并 |
| 部署 | Vercel | 零配置，与 Next.js 原生集成 |

---

## 3. 色彩与字体系统

```ts
// tailwind.config.ts 中定义
colors: {
  navy:   { DEFAULT: '#1B2B5E', light: '#2D3F7A', muted: '#4A5F9E', 50: '#EEF1F9' }
  signal: { DEFAULT: '#22C55E', muted: '#DCFCE7', text: '#166534' }
  bg:     { gray: '#F5F6F8' }
}

fontFamily: {
  heading: ['Spectral', ...serif]        // 价格数字、大标题
  sans:    ['DM Sans', 'PingFang SC'...] // 正文、UI 标签
  mono:    ['JetBrains Mono', ...]       // SYS.XXX、技术标签
}
```

设计原则：
- 信号绿（#22C55E）是唯一高亮色，专属于"值得买"信号
- 深海军蓝（#1B2B5E）是主色，体现判断感与可信度
- 卡片背景统一白色，页面背景 #F5F6F8，形成视觉层次
- SYS.XXX 系统编号用 Mono 字体，强化"AI 已审阅"的质感

---

## 4. 页面结构

### 4.1 登录页 `/`

布局：左右分栏（55% / 45%）

左侧：
- 品牌标识（圆点 + FareSniper mono 字）
- 实时监测徽章（呼吸动画绿点）
- 大标题：「好机票，不等人。」（Spectral italic）
- 副文案 + 微信登录按钮 + 手机号登录
- 社会证明（用户头像叠加 + 数量）

右侧（grain 纹理底）：
- 标签「你上次搜索后可能错过的」
- 一张默认旋转 3° 的 Deal 预览卡，hover 自动归正
- 卡片包含：SYS.ID、路线、价格/折扣、航司日期、信号标签、AI 判断栏

### 4.2 对话页 `/chat`

布局：全屏中心 + 四角浮动卡

中心：
- 大标题「想去哪？」（Spectral）
- 自然语言输入框（圆角、focus 动效）
- 快捷建议 pill 按钮

四角浮动卡：
- 4 张小尺寸 Deal 卡，错峰漂浮动画（drift-a/b/c/d，间隔 1-2s）
- 仅展示目的地渐变图 + 价格 + 信号标签
- pointer-events-none，不干扰输入

### 4.3 用户记忆页 `/memory`

布局：单列，max-w-[480px] 居中

- 每条记忆一张白卡，随机 ±2° 倾斜（物理叠层感）
- 顶部彩色条区分记忆类型（accentColor 字段）
- hover：倾斜归零 + 上移 2px + 阴影加深 + 显示编辑/删除按钮
- inline 编辑（Enter 保存，Escape 取消）
- 底部「添加偏好」虚线卡

### 4.4 用户探索页 `/explore`

布局：横向滚动卡列表

- 每张卡 272px 宽，含：
  - 目的地渐变封面（CSS gradient 模拟）
  - 左上：置信度彩点徽章
  - 右上：SYS.XXX mono 编号
  - 底部叠加：路线文字
  - 卡体：大号价格（Spectral）、折扣率、信号标签、AI 判断栏
- hover：-translate-y-2 + shadow-card-float
- 顶部筛选 pills（全部 / 高置信 / 符合偏好 / 今日新增）
- 底部固定 CTA 条（深色背景 + 「开始对话」按钮）

---

## 5. 目录结构

```
frontend/
├── app/
│   ├── layout.tsx            # 字体注入 + 全局 metadata
│   ├── globals.css           # CSS 变量、动画 keyframes、scrollbar
│   ├── page.tsx              # 登录页
│   ├── chat/page.tsx         # 对话开始页
│   ├── memory/page.tsx       # 用户记忆页
│   └── explore/page.tsx      # 用户探索页
├── lib/
│   ├── api-client.ts         # 统一请求层，支持 MOCK/REMOTE 切换
│   └── mocks.ts              # 所有 mock 数据（按接口形状构造）
├── types/
│   └── index.ts              # FlightDeal、PreferenceMemory 等类型
├── tailwind.config.ts        # 色彩 / 字体 / 阴影 / 动画扩展
└── next.config.mjs
```

---

## 6. 数据类型

```ts
// types/index.ts

export type FlightDeal = {
  id: string
  origin: string; originCode: string
  destination: string; destinationCode: string
  price: number; originalPrice: number
  departDate: string; airline: string
  departTime: string; arriveTime: string
  signals: string[]
  confidence: 'high' | 'medium' | 'low'
  systemId: string          // 'SYS.042' 格式，AI 审阅编号
  gradientFrom: string; gradientTo: string
  verdict: string           // AI 自然语言判断
}

export type PreferenceMemory = {
  id: string
  field: string             // 字段 key，如 'price_anchor'
  label: string             // 展示名，如 '心理价位'
  value: string
  source: 'manual' | 'auto'
  updatedAt: string
  accentColor: string       // 卡片顶部色条颜色
  rotation: string          // 倾斜角度，如 '-1deg'
}
```

---

## 7. API 接入层

`lib/api-client.ts` 通过环境变量 `NEXT_PUBLIC_API_MODE` 切换数据源：

```ts
const MODE = process.env.NEXT_PUBLIC_API_MODE ?? 'mock'

export async function searchFlights(message: string, userId: string) {
  if (MODE === 'mock') return mockSearchResult(message)
  return fetch('/api/search', { method: 'POST', body: JSON.stringify({ message, user_id: userId }) })
    .then(r => r.json())
}

export async function getMemory(userId: string) {
  if (MODE === 'mock') return mockMemories
  return fetch(`/api/memory?user_id=${userId}`).then(r => r.json())
}

export async function getRecommendations(userId: string) {
  if (MODE === 'mock') return mockDeals
  return fetch(`/api/recommendations?user_id=${userId}`).then(r => r.json())
}
```

切换方式：`.env.local` 中设置：
```
NEXT_PUBLIC_API_MODE=mock      # 本地开发
NEXT_PUBLIC_API_MODE=remote    # 接入真实后端
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 8. SSE 流式接入（AI 推荐）

`lib/sse.ts` 封装 SSE 连接：

```ts
export function streamChat(message: string, userId: string, callbacks: {
  onStatus: (msg: string) => void
  onPartial: (text: string) => void
  onFinal: (result: FlightDeal[]) => void
  onError: (err: string) => void
}) {
  const es = new EventSource(`/api/chat?message=${encodeURIComponent(message)}&user_id=${userId}`)
  es.addEventListener('status', e => callbacks.onStatus(e.data))
  es.addEventListener('partial_recommendation', e => callbacks.onPartial(e.data))
  es.addEventListener('final_result', e => { callbacks.onFinal(JSON.parse(e.data)); es.close() })
  es.addEventListener('error', e => { callbacks.onError('连接中断'); es.close() })
  return () => es.close() // cleanup
}
```

前端表现：
- 有流时显示「AI 正在判断是否值得买…」
- SSE 中断自动降级到普通请求结果

---

## 9. 状态策略

| 状态 | 管理方式 |
|---|---|
| 用户 ID | Context（全局） |
| 偏好缓存 | Context + localStorage |
| 搜索结果列表 | 页面级 useState |
| 推荐文案 / SSE 流 | 页面级 useState |
| loading / error / empty | 页面级 useState |

无 Redux、无 Zustand、无事件总线。

---

## 10. 动画规范

| 动画 | 触发时机 | 实现 |
|---|---|---|
| 浮动卡漂浮 | 页面挂载 | drift-a/b/c/d keyframes，错峰延迟 |
| 信号绿呼吸点 | 常驻 | animate-ping（Tailwind 内置）|
| 卡片倾斜归正 | hover | CSS transform transition 300ms |
| 卡片浮起 | hover | -translate-y-2 + shadow 加深 |
| 输入框聚焦 | focus | border-color + shadow transition |
| 记忆卡 inline 编辑 | 点击编辑 | input 替换文字，Enter 保存 |

---

## 11. 前后端协作边界

前端负责：
- 全部页面、组件、交互、动效
- `api-client.ts` 请求封装
- mock 数据（按最终接口形状构造）
- loading / empty / error 态展示

前端不负责：
- 意图解析（自然语言 → 结构化查询）
- 航班排序与价格判断
- 偏好推理
- 任何 AI 决策逻辑

后端需保证：
- `/api/search` 返回 `FlightDeal[]` + `Recommendation`
- `/api/memory` GET/PATCH 字段稳定
- `/api/recommendations` 返回 `FlightDeal[]`
- SSE 事件类型固定：`status` / `partial_recommendation` / `final_result` / `error`
- 错误码可识别（前端按 code 决定提示文案）

---

## 12. 启动与部署

```bash
# 本地开发
cd frontend && npm run dev
# → http://localhost:3000（或自动递增端口）

# 生产构建
npm run build && npm start

# 切换到真实后端
echo "NEXT_PUBLIC_API_MODE=remote\nNEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local
```
