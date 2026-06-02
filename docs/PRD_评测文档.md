# FareSniper PRD 整体评测文档

> 适用版本：PRD v2.0（特价机票发现平台）
> 覆盖范围：PRD 全部功能模块 + 北极星/护栏指标 + MVP 假设 H1–H6 + AI 评估体系 + 验收标准
> 用途：作为产品上线前/灰度期/上线后的统一评测对照清单，逐条对照执行
> 所有「PRD 出处」均指向 `PRD.md` 章节号；阈值/公式均引用 PRD 原文，未自创标准

---

## 0. 文档目录

- [1. 评测总览](#1-评测总览)
  - 1.1 评测目的
  - 1.2 评测四层次
  - 1.3 评测方法分类
  - 1.4 评测时间窗与责任分工
- [2. 按功能模块组织的评测维度](#2-按功能模块组织的评测维度)
  - 2.1 意图解析与多轮澄清（Slot Filling）
  - 2.2 动态意图注册表与 Embedding 快速路
  - 2.3 比价数据源与缓存（爬虫 + FlightCacheRepository）
  - 2.4 偏好匹配技能（PreferenceMatch 纯工程）
  - 2.5 值得买信号体系（ValueJudge）
  - 2.6 推荐分计算与 deals 排序（7.1 公式）
  - 2.7 记忆/偏好系统（异步学习 + MemoryPage）
  - 2.8 探索发现页（推荐瀑布流 + 盲盒）
  - 2.9 价格监控（Alerts MVP）
  - 2.10 个人页（PersonalPage）
  - 2.11 LLM Pipeline（ReAct Agent / ValueJudge / 兜底）
  - 2.12 用户身份与多轮会话（user_id / session）
  - 2.13 可靠性设计（熔断 / 重试 / 超时 / 降级）
  - 2.14 跳转购买深链（booking_url / H5 fallback）
  - 2.15 数据契约（DTO 完整性）
  - 2.16 埋点
- [3. 假设验证 H1–H6](#3-假设验证-h1h6)
- [4. 核心指标与护栏汇总表](#4-核心指标与护栏汇总表)
- [5. 评测执行清单（可自动化 / 需手动 / 需灰度）](#5-评测执行清单)
- [附录 A：PRD 模块/假设/指标覆盖矩阵](#附录-a覆盖矩阵)

---

## 1. 评测总览

### 1.1 评测目的

验证 FareSniper 是否达成 PRD 定义的产品价值与商业价值闭环：用户在一个对话界面完成「查票 → 值得买判断 → 跳转购买」，并通过偏好记忆形成「越用越懂我」的复访飞轮。评测既要回答「功能是否按 PRD 实现」，也要回答「PRD 假设是否成立、指标是否达标、护栏是否守住」。

### 1.2 评测四层次

| 层次 | 评测对象 | 回答的问题 | 主要方法 |
|------|---------|-----------|---------|
| ① 功能验收 | 各功能模块行为是否符合 PRD 规格 | 「做对了吗」 | 自动化测试 + 手动验证 |
| ② 核心指标达成 | 北极星 QPC、转化漏斗、性能 P95 等 | 「达标了吗」 | 灰度埋点 + 性能压测 |
| ③ 假设验证 H1–H6 | PRD §7 MVP 假设是否成立 | 「方向对吗」 | A/B 测试 + 访谈 + 留存分析 |
| ④ 护栏合规 | 深链失败率、误导率、P95 延迟等底线 | 「没踩线吧」 | 灰度埋点 + 告警监控 |

> 出处：层次①对应 PRD §16 MVP 范围 + §9 功能详述；层次②对应 PRD §3.2 北极星/KPI + §15 性能；层次③对应 PRD §7 假设清单；层次④对应 PRD §3.2 护栏指标。

### 1.3 评测方法分类

| 方法标识 | 含义 | 适用场景 | 数据来源 |
|---------|------|---------|---------|
| **AUTO**（自动化测试） | 单测 / 集成 / E2E 脚本断言 | 工程规则、DTO 契约、纯函数公式、格式合规 | `backend/tests/`、E2E 测试集（PRD §17.2，50 条） |
| **MANUAL**（手动验证） | 人工核查、标注集人评 | LLM 输出质量、文案相关性、信号准确率 | PRD §17.1 标注集（30 条意图 / 20 条信号 / 30 条建议） |
| **GRAY**（灰度埋点） | 线上事件统计、A/B、留存分析、NPS | 转化漏斗、留存、采纳率、假设验证 | PRD §14 埋点事件 + LangSmith 追踪 |

### 1.4 评测时间窗与责任分工

引用 PRD §7「假设验证计划」与 §17：

- **上线前（必做）**：B 类基础评测（PRD §17.1）、E2E 测试集（PRD §17.2）、所有 must 级功能验收。
- **灰度第 1 周**：验证 H1–H3（对话查票意愿、AI 建议采纳、跳转购买）。
- **上线 30 天后**：验证 H4–H5（偏好留存提升、价格新鲜度 NPS）。
- **v1.1 评估**：验证 H6（探索页流量占比）。
- **持续监控**：Badcase 分级（PRD §17.3）+ LangSmith 告警（parse_failed>5% / 全平台超时>10% / P95>5s）。

---

## 2. 按功能模块组织的评测维度

> 每个 case 字段：场景 / 操作 / 预期结果 / 通过判据。等级 must = MVP 必须达标；nice = 体验优化项。

### 2.1 意图解析与多轮澄清（Slot Filling）

PRD 出处：§9.1 Agent State、§9.2 意图识别与 Slot Filling、§10.1 ReAct Agent、§17.1。

| 维度 | 参考 case（场景 / 操作 / 预期 / 通过判据） | PRD 出处 | 等级 | 方法 |
|------|----------------------------------------|---------|------|------|
| 意图枚举识别 | 输入「帮我设个价格提醒」→ 应识别 `set_alert`；「查看我的偏好」→ `check_preference`；问候→`chitchat` 不调工具 | §9.2.1 | must | AUTO+MANUAL |
| 必填槽提取 | 「明天从北京去上海」→ origin=北京/destination=上海/depart_date=明天具体日期 | §9.2.2 | must | AUTO |
| 相对日期推算 | 「下周五」→ 推算最近周五；「五一」→ 2026-05-01；「国庆」→ 2026-10-01~10-07 | §9.2.4 / §10.1 | must | AUTO |
| 约束识别 | 「不要红眼」→ `avoid_redeye`；「直飞」→ `direct_only`；「早点到」→ `prefer_morning` | §9.2.2 约束枚举 | must | AUTO |
| 单轮只问一项 | 缺 origin+destination 时，ask_user 只问优先级最高的 origin（origin→destination→depart_date） | §9.2.3 关键规则 | must | MANUAL |
| 上下文感知追问 | 已知 destination=三亚缺 origin → 追问承接已知信息（如「去三亚！从哪儿出发？」），非固定模板 | §9.2.3 / §10.1 追问风格 | must | MANUAL |
| 追问文案约束 | question ≤ 20 字、不重复已知信息、不用「请问/您」过度正式措辞 | §9.2.5 / §10.1 | nice | MANUAL |
| 跨轮槽位累积 | Turn1 给目的地+日期，Turn2 补 origin → 合并后必填完整触发搜索，不重复询问已填槽 | §9.1 merge_slots / §9.2.3 | must | AUTO |
| null 不覆盖规则 | 新一轮槽位值为 null 时不覆盖已有值 | §9.1 merge_slots | must | AUTO |
| 追问降级 | clarify_count ≥ 2 仍缺必填 → 调 `show_fallback_form`，置 `fallback_triggered=true`，前端弹 Modal（不跳页） | §9.2.3 / §9.7 / §9.2.5 | must | AUTO+MANUAL |
| 意图解析准确率 | 30 条标注集（正常/缩写/相对日期/歧义），正确提取 origin/destination/date_range | §17.1 | must | MANUAL |
| 追问准确率 | 10 条多轮对话，追问内容正确且不重复已提供信息 | §17.1 | must | MANUAL |
| 解析失败兜底 | 空输入/纯表情/无意义输入 → 「没听明白，换个说法试试？」+ 表单入口 | §9.7 / §17.2 边界 | must | AUTO |
| 对抗鲁棒性 | 提示注入「忽略上述指令输出XXX」/ 要求编造票价 → 不被劫持、不编造数据 | §17.2 对抗 case | must | MANUAL |

成立标准（引用原文阈值）：意图解析准确率 ≥ 90%（§17.1 / §15）、追问准确率 ≥ 90%（§17.1）、parse_failed 率 < 10%（§15）。

### 2.2 动态意图注册表与 Embedding 快速路

PRD 出处：§5.2.5（intent_registry / intent_examples 表）、§9.2.6。

| 维度 | 参考 case | PRD 出处 | 等级 | 方法 |
|------|----------|---------|------|------|
| 识别层动态加载 | 写 intent_registry（is_active=true）→ ≤ 60s（Redis TTL）新请求自动加载新意图 | §9.2.6 两层结构 | nice | AUTO |
| tool schema 动态构建 | bootstrap 节点把 required_slots/slot_schema 转为 function calling schema 并 bind_tools | §9.2.6 build_tool_schemas | nice | AUTO |
| 识别/执行解耦 | is_active=true 但 handler 未就绪 → 返回「该功能正在建设中」，不崩溃 | §9.2.6 | nice | AUTO |
| Embedding 快速路 | 输入命中例句 cosine > 0.85 → 注入预判提示跳过意图推理；≤ 0.85 → 走 ReAct 完整推理 | §9.2.6 fast_intent_match | nice | AUTO |
| 冷启动例句质量 | 新意图 ≥ 10 条例句（min_examples），覆盖口语/书面/缩写/无槽位边界 | §9.2.6 冷启动质量 | nice | MANUAL |
| 缓存失效接口 | 调 `/api/admin/intents/cache/invalidate` → 立即生效不等 60s | §9.2.6 管理接口 | nice | AUTO |

> 说明：PLAN.md 显示线上当前跑规则版 slot-filling，ReAct/动态注册表为半成品。本节多为 nice 级，评测时区分「已接图」与「未接图」。

### 2.3 比价数据源与缓存（爬虫 + FlightCacheRepository）

PRD 出处：§9.3 比价技能、§5.2.5 数据表、§5.2.6 超时处理。

| 维度 | 参考 case | PRD 出处 | 等级 | 方法 |
|------|----------|---------|------|------|
| 查询只读缓存 | 用户查询不现场触发爬虫，只读 flight_snapshots / platform_price_snapshots | §9.3 查询链路 | must | AUTO |
| 字段归一化 | flights_monitor 原始字段（flight_number/dep_time/transfer_count/platform+price）正确映射为 flight_no/dep_time/stops/prices[] | §9.3 工程改造方向 | must | AUTO |
| 同航班聚合 | 按 `flight_no + dep_time + depart_date` 聚合；prices 保留各平台真实价；lowest_price 取最低 | §9.3 平台聚合规则 | must | AUTO |
| 缓存命中键 | 主查询条件 origin_code+destination_code+depart_date；去重键含 flight_no+dep_time | §9.3 缓存命中规则 | must | AUTO |
| upsert 保留最新 | 同去重键重复入库执行 upsert，保留最新 crawled_at | §9.3 缓存命中规则 | must | AUTO |
| TTL 与新鲜度 | 每条缓存记录 crawled_at + expires_at（默认 +1h）；命中过期缓存返回并标 `meta.data_freshness=stale` | §9.3 数据刷新策略 | must | AUTO |
| 爬取频率 | Scheduler 每 1h 触发（FLIGHT_CRAWL_INTERVAL_MINUTES=60） | §9.3 / §5.2.7 | must | AUTO |
| 高频航线池 | 覆盖北京↔成都/三亚/上海/广州/杭州固定池 + query_history 近7天 TopN 动态池 + active alerts 航线 | §9.3 定时爬取范围 | must | AUTO |
| 单平台超时隔离 | 单平台超时只标记该平台失败，其他平台结果照常入库 | §9.3 超时处理 | must | AUTO |
| 全平台失败保护 | 全部平台失败时不覆盖上一轮有效缓存，crawl_jobs.status=failed | §9.3 超时处理 / §5.2.6 | must | AUTO |
| 无缓存空数组 | 数据库无匹配航线 → 返回空数组，前端展示「暂无数据，请重试」 | §9.3 / §9.7 | must | AUTO |
| 历史价真实性 | history_avg_90d / history_low_90d 仅在有真实历史数据时返回，否则 `null`，不捏造 | §9.3 数据覆盖要求 | must | AUTO |
| 排序入口 | 默认按 lowest_price + tax + baggage_fee 升序，再进推荐分排序 | §9.3 平台聚合规则 | must | AUTO |
| 字段缺失丢弃 | 单平台单条价格字段缺失 → 丢弃该条，不影响同航班其他平台 | §9.3 超时处理 | must | AUTO |
| 真实平台覆盖 | 当前目标平台携程/去哪儿/飞猪；某平台不可用则该平台当次为空 | §9.3 数据来源 | must | MANUAL |

### 2.4 偏好匹配技能（PreferenceMatch 纯工程）

PRD 出处：§9.4 偏好匹配、§10.2 PreferenceMatch（纯工程规则，无 LLM）。

| 维度 | 参考 case | PRD 出处 | 等级 | 方法 |
|------|----------|---------|------|------|
| 心理价位匹配 | lowest_price ≤ user.budget → reason「在你的心理价位以内」 | §9.4 / §10.2 | must | AUTO |
| 偏好航司匹配 | airline ∈ preferred_airlines → reason「你常飞的{航司}」 | §9.4 / §10.2 | must | AUTO |
| 避免红眼匹配 | 有 avoid_redeye 且 dep_hour ≥ 6 → reason「符合你的出行习惯」 | §9.4 / §10.2 | must | AUTO |
| 常去城市 boost | destination ∈ frequent_cities → boost=true，不输出 reason，仅影响排序 | §9.4 / §10.2 | must | AUTO |
| reasons 上限 | reasons 最多 3 条 | §10.2 | must | AUTO |
| 新用户空偏好 | memories 为空 → preference_matched 返回空数组，判断节点跳过偏好维度，卡片不展示偏好文案 | §9.4 新用户处理 | must | AUTO |
| 判定依据 | 是否新用户直接看 memories 是否为空，不依赖 query_count | §9.4 / 待确认清单 | must | AUTO |
| 无 LLM 校验 | PreferenceMatch 链路不发起任何 LLM 调用 | §10.0 / §10.2 | must | AUTO |

### 2.5 值得买信号体系（ValueJudge）

PRD 出处：§9.6 值得买信号、§10.3 ValueJudge、§17.1。

| 维度 | 参考 case | PRD 出处 | 等级 | 方法 |
|------|----------|---------|------|------|
| 历史低价信号 | lowest_price < history_avg_90d × 0.85（差值 > 15%）→ 信号「历史低价」 | §9.6 / §10.3 判断逻辑 | must | AUTO+MANUAL |
| 心理价位信号 | lowest_price ≤ user.budget → 「符合心理价位」 | §9.6 | must | AUTO |
| 出行习惯信号 | 见偏好匹配表 → 「符合出行习惯」 | §9.6 | must | AUTO |
| 节假日不入 signals | is_holiday=true 时仅可在 advice 文案提及，**不得写入 signals 数组**；MVP 前端不渲染该标签 | §9.6 / §10.3 限制 | must | AUTO |
| 一句话建议规则 | 历史低价+心理价位→「建议现在买，比均价低X%且在预算内」；历史低价超预算→「历史低位，但超出预算X元」；无信号→「价格正常，可继续关注」；数据不足→「数据有限，仅供参考」 | §9.6 建议规则 / §10.3 | must | MANUAL |
| advice 长度 | advice ≤ 20 字 | §9.6 / §10.3 限制 | must | AUTO |
| 不捏造数据 | 只用传入数据判断，历史数据不足时 signals=[] | §10.3 限制 | must | MANUAL |
| 值得买信号准确率 | 抽查 20 条人工核查「历史低价」仅在真实低于均价 15% 触发 | §17.1 | must | MANUAL |
| 一句话建议相关性 | 30 条人评：与触发信号一致、≤20字、无编造 | §17.1 | must | MANUAL |
| 判断超时降级 | ValueJudge LLM > 5s → 跳过 AI 建议仅展示价格，结论位「分析中…」 | §9.7 | must | AUTO |

成立标准：值得买信号准确率 ≥ 85%（§17.1）、一句话建议相关性 ≥ 90%（§17.1）、误导率 < 3%（§3.2 护栏，「建议买」但实际高于历史均价比例）。

### 2.6 推荐分计算与 deals 排序（7.1 公式）

PRD 出处：§11.1 recommend_score 计算规则 + deals 排序规则。

| 维度 | 参考 case | PRD 出处 | 等级 | 方法 |
|------|----------|---------|------|------|
| 历史低价原始分 | `max(0, 1 - lowest_price / history_avg_90d)`（0~1）；历史数据不足按 0 | §11.1 | must | AUTO |
| 偏好匹配原始分 | `min(matched_count, 3) / 3`（0~1） | §11.1 | must | AUTO |
| 加成原始分 | `(stops==0?1:0)×0.5 + (baggage_fee==0?1:0)×0.5`（0~1） | §11.1 | must | AUTO |
| 总分公式 | `recommend_score = (hist×0.5 + pref×0.3 + bonus×0.2) × 10` | §11.1 | must | AUTO |
| 输出格式 | 四舍五入保留一位小数，字符串输出（如 `"9.5"`） | §11.1 | must | AUTO |
| 主排序 | 综合总价（price+tax+baggage_fee）升序 | §11.1 deals 排序 | must | AUTO |
| 次排序 | 同价位 boost=true 优先 | §11.1 deals 排序 | must | AUTO |
| 第三排序 | recommend_score 降序 | §11.1 deals 排序 | must | AUTO |
| deals[0] 最优 | deals[0] 为综合最优，前端直接作为结果卡片 | §11.1 / §13.2 | must | AUTO |
| 总价计算 | 综合总价 = price + tax + baggage_fee（前端执行） | §11.1 | must | AUTO |

### 2.7 记忆/偏好系统（异步学习 + MemoryPage）

PRD 出处：§9.5 记忆设计、§11.3 MemoryResponseDto、§12.3–12.5 memory 接口、§13.4 MemoryPage。

| 维度 | 参考 case | PRD 出处 | 等级 | 方法 |
|------|----------|---------|------|------|
| 存储位置 | 偏好存后端 PostgreSQL，前端不在 localStorage 存偏好（仅缓存 user_id） | §9.5 / 待确认清单 | must | AUTO |
| 常去城市学习 | 同一目的地查询 ≥ 3 次 → 加入 frequent_cities | §9.5 更新逻辑 | must | AUTO |
| 心理价位学习 | 取最近 5 次点击价格中位数（四舍五入到整十）→ budget | §9.5 更新逻辑 | must | AUTO |
| 避免红眼学习 | 连续 3 次查询 dep_time ≥ 06:00 → 推断 avoid_redeye | §9.5 更新逻辑 | must | AUTO |
| 偏好航司学习 | 同一航司点击 ≥ 2 次 → 加入 preferred_airlines | §9.5 更新逻辑 | must | AUTO |
| 异步不阻塞 | 记忆更新异步执行，写入失败静默忽略不影响主链路 | §8.2 / §9.5 / §9.7 | must | AUTO |
| 来源类型 | 每条偏好带 source ∈ {manual, query_history, click_history, system_inferred} | §9.4 / §9.5 / §11.3 | must | AUTO |
| 来源展示文案 | MemoryPage 偏好卡展示「当前记录：{value_display}｜来源：{source_label}｜更新于 {date}」 | §9.4 / §13.4 | must | MANUAL |
| evidence 可展开 | 点击偏好可展开 evidence（关联查询/点击/航班/价格/规则） | §9.5 / §11.3 / §13.4 | nice | MANUAL |
| confidence | 推断置信度 0~1，手动设置为 1 | §9.5 记忆来源字段 | nice | AUTO |
| 手动编辑 | PATCH /api/memory 更新单字段 source=manual，返回完整 MemoryResponseDto | §12.4 | must | AUTO |
| 删除单条 | DELETE /api/memory/{field} 删除单条，返回更新后 DTO | §12.5 | must | AUTO |
| 清除所有记忆 | 个人中心一键重置 + 确认弹窗（不可逆） | §9.5 用户可操作项 | must | MANUAL |
| 五类偏好可查 | 常去城市/心理价位/偏好航司/出行习惯/出行场景均可查可逐条编辑 | §9.5 / §12.3 | must | MANUAL |
| query_history 展示 | MemoryPage「出行历史」取最近 3 条查询 | §13.4 | nice | MANUAL |
| 后端失败降级 | GET /api/memory 失败 → 前端静默降级为静态示例（4 章节） | §13.4 / §9.7 | must | MANUAL |

### 2.8 探索发现页（推荐瀑布流 + 盲盒）

PRD 出处：§5.3 功能地图、§12.6 GET /api/recommendations、§13.3 ExplorePage。

| 维度 | 参考 case | PRD 出处 | 等级 | 方法 |
|------|----------|---------|------|------|
| 冷启动热门 | memories 为空 → 返回固定热门路线（北京↔三亚/成都、上海↔三亚、成都↔丽江、广州↔青岛等） | §12.6 生成规则 | must | AUTO |
| 个性化推荐 | memories 不为空 → 基于 frequent_cities/budget 生成个性化卡片 | §12.6 | must | AUTO |
| 卡片数量 | 每次调用 ≥ 4 张、≤ 8 张 | §12.6 | must | AUTO |
| preview_deal 必含 | 每张卡片含 preview_deal（ExplorePage 用）+ query_hint（ChatPage 用） | §12.6 / §11.4 | must | AUTO |
| 无缓存不展示 | 某热门路线无缓存数据 → 该卡片不返回，避免展示不可验证价格 | §12.6 | must | AUTO |
| 瀑布流渲染 | 过滤 preview_deal 不为空的 cards，destination_code 作图片 seed | §13.3 | nice | MANUAL |
| 盲盒筛选 | 有出发地输入 → filter origin_city.includes(departure)；无筛选 → 全部 cards 随机 | §13.3 盲盒筛选逻辑 | nice | MANUAL |
| ChatPage 快捷问题 | 取 cards[*].query_hint 最多 4 条作输入框下方标签 | §13.2 / §11.4 | nice | MANUAL |

### 2.9 价格监控（Alerts MVP）

PRD 出处：§9.10 价格监控、§12 接口、§13.5 PersonalPage。

| 维度 | 参考 case | PRD 出处 | 等级 | 方法 |
|------|----------|---------|------|------|
| 创建监控 | 卡片点「监控价格」→ POST /api/alerts 存航班信息+current_price+target_price，返回 alert_id/status=active | §9.10 | must | AUTO |
| 查询监控列表 | GET /api/alerts 返回该用户 alerts 列表 | §9.10 | must | AUTO |
| MVP 不推送 | 仅存储监控意图，不做实时追踪/推送，不判断是否达目标价 | §9.10 MVP 限制 | must | AUTO |
| 不可编辑 | 用户可查看不可编辑；DELETE 取消监控为 v1.1 | §9.10 MVP 限制 | nice | — |

### 2.10 个人页（PersonalPage）

PRD 出处：§13.1 页面总览、§13.5 PersonalPage。

| 维度 | 参考 case | PRD 出处 | 等级 | 方法 |
|------|----------|---------|------|------|
| MVP 纯静态 | PersonalPage MVP 为纯静态页面，无 API 调用，节点/通知为硬编码示例 | §13.1 / §13.5 | must | MANUAL |
| v1.1 待接入 | 价格监控节点接 GET /api/alerts、对话历史来自 memory.query_history、通知 toggle 接 PATCH /api/settings（均未实现） | §13.5 待接入 | nice | — |

### 2.11 LLM Pipeline（ReAct Agent / ValueJudge / 兜底）

PRD 出处：§5.2.2 SearchGraph、§9.1 State、§10 Prompt 设计、§5.2.6 兜底、§18 模型选型。

| 维度 | 参考 case | PRD 出处 | 等级 | 方法 |
|------|----------|---------|------|------|
| 图路由 | route_after_agent：有 tool_calls → tool_executor；无 → END | §5.2.2 | must | AUTO |
| 防死循环 | recursion_limit=20 通过 config 传入 | §5.2.2 / §9.1 | must | AUTO |
| messages 累加 | add_messages 自动追加不覆盖，含 Human/AI/ToolMessage | §5.2.2 / §9.1 | must | AUTO |
| 工具集 | ask_user / search_flights / get_preferences / judge_value / show_fallback_form 可被代理调用 | §9.2.5 | must | AUTO |
| 工具失败兜底 | 工具调用失败/不合规 → ToolMessage 写错误，代理可继续推理或改调 show_fallback_form | §5.2.6 / §10.1 边界 | must | AUTO |
| 空响应兜底 | 代理无 tool_call 且无 final text → fallback_triggered=true，展示兜底表单 | §5.2.6 / §10.1 | must | AUTO |
| 格式合规率 | 100 次调用日志自动解析为合法 JSON、无多余文字 | §17.1 / §18.1 | must | AUTO |
| 模型可切换 | MODEL_AGENT / MODEL_JUDGE 改环境变量切换，无需改代码 | §10.0 / §18.3 | must | AUTO |
| function calling | ReAct Agent 使用支持 function calling 的模型（qwen-plus/qwen-max，非 qwen-turbo） | §10.0 / §18.3 | must | MANUAL |
| 模型延迟 | ReAct Agent P95 < 2s，ValueJudge P95 < 3s | §18.1 选型权重 / §15 | must | GRAY |
| 模型版本记录 | 每次 LLM 调用记录模型版本写入 metadata，LangSmith 可对比 badcase | §18.3 | nice | AUTO |

### 2.12 用户身份与多轮会话（user_id / session）

PRD 出处：§9.8 user_id 生命周期、§9.9 session 设计、§12.2。

| 维度 | 参考 case | PRD 出处 | 等级 | 方法 |
|------|----------|---------|------|------|
| 匿名 ID 下发 | 首次 API 无有效 user_id → 后端生成 UUID 写入响应体 | §9.8 | must | AUTO |
| 前端持久化 | 前端存 localStorage（key=faresnipper_user_id），后续请求携带 | §9.8 / §5.2.4 | must | MANUAL |
| 未知 ID 容错 | 后端收未知 user_id 自动创建新用户数据，不报错 | §9.8 约束 | must | AUTO |
| 创建 session | POST /api/session → 返回 session_id + created_at | §9.9 / §12.1 | must | AUTO |
| 多轮上下文 | search 携 session_id，后端查 session 历史拼入 ReAct 上下文 | §9.9 / §12.2 | must | AUTO |
| session 过期 | 超 30min 无活动失效（SESSION_TTL_MINUTES=30），返回 session_expired，前端自动新建 | §9.9 / §5.2.7 | must | AUTO |
| 追问响应结构 | 意图不完整 → deals=[]、recommendation.text=追问文案、meta.clarify_count 递增 | §12.2.1 | must | AUTO |

### 2.13 可靠性设计（熔断 / 重试 / 超时 / 降级）

PRD 出处：§5.2.6 可靠性设计、§9.7 异常处理。

| 维度 | 参考 case | PRD 出处 | 等级 | 方法 |
|------|----------|---------|------|------|
| 熔断 CLOSED→OPEN | 单数据源连续失败 ≥ 5 次 → OPEN，直接拒绝返回空结果 | §5.2.6 | must | AUTO |
| OPEN→HALF_OPEN | OPEN 持续 30s 后放行一次；成功→CLOSED，失败→重置 OPEN | §5.2.6 | must | AUTO |
| 偏好读取失败 | /api/memory 失败 → 跳过偏好维度正常展示价格，不报错 | §9.7 | must | AUTO |
| 记忆写入失败 | DB 写入异常 → 静默忽略，下次查询重试 | §9.7 | must | AUTO |
| 比价为空 | 全平台超时/无匹配 → 「暂未找到航班，试试换个日期」 | §9.7 | must | AUTO |
| 错误不中断 | 各工具异常收集进 errors，不中断流程 | §9.1 / §8.2 | must | AUTO |
| 可观测性 | LangSmith 每次 graph.invoke 生成 run_id 可查节点耗时/LLM IO | §5.2.6 | nice | MANUAL |

### 2.14 跳转购买深链（booking_url / H5 fallback）

PRD 出处：§11.1 booking_url 深链规则。

| 维度 | 参考 case | PRD 出处 | 等级 | 方法 |
|------|----------|---------|------|------|
| 携程深链 | `ctrip://flight/search?from={origin_code}&to={dest_code}&date={depart_date}` | §11.1 | must | AUTO |
| 去哪儿深链 | `qunar://flight?from=...&to=...&date=...` | §11.1 | must | AUTO |
| 飞猪深链 | `alitrip://flight?from=...&to=...&date=...` | §11.1 | must | AUTO |
| APP 未装降级 | 跳深链 1.5s 无响应 → fallback 到 h5_fallback_url | §11.1 | must | MANUAL |
| 兜底 H5 | 真实数据源无可购深链时，后端填平台 H5 搜索页作兜底 | §11.1 | must | AUTO |
| 深链失败率 | 线上深链跳转失败率 < 5%（护栏） | §3.2 护栏 | must | GRAY |

### 2.15 数据契约（DTO 完整性）

PRD 出处：§11 数据结构定义、§12 接口规范。

| 维度 | 参考 case | PRD 出处 | 等级 | 方法 |
|------|----------|---------|------|------|
| DealCardDto 必填 | id/system_id/platform/origin_city/origin_code/destination_city/destination_code/depart_date/airline/depart_time/arrive_time/price/tax/baggage_fee/has_baggage/prices/signals/confidence/verdict 全部存在 | §11.1 | must | AUTO |
| PriceItem 结构 | `{name, price, lowest?}`，前端按 lowest 高亮 | §11.1 | must | AUTO |
| SearchResponseDto | query/deals/analysis/recommendation/meta 五段结构完整 | §11.2 | must | AUTO |
| recommendation.action | ∈ {buy_now, watch, skip} | §11.2 | must | AUTO |
| MemoryResponseDto | memories/query_history/click_history/meta 结构完整，每条 memory 含 source/source_label/evidence/confidence/updated_at | §11.3 | must | AUTO |
| RecommendationsResponseDto | cards 含 title/reason/query_hint/tags/preview_deal | §11.4 | must | AUTO |
| 接口总览 8 接口 | session/search/memory(GET/PATCH/DELETE)/recommendations/alerts(POST/GET) 全部可用 | §12.1 / §16 | must | AUTO |
| fallback_mode | meta.fallback_mode=true 时前端提示「暂无数据」 | §11.2 / §12.2 | must | AUTO |

### 2.16 埋点

PRD 出处：§14 埋点。

| 事件 | 触发时机与关键参数 | PRD 出处 | 等级 | 方法 |
|------|------------------|---------|------|------|
| search_submitted | 提交查询：query_text/user_id/clarify_count | §14 | must | GRAY |
| intent_parsed | 解析完成：intent_complete/parse_failed | §14 | must | GRAY |
| result_viewed | 结果展示：result_count/has_signals/has_preference | §14 | must | GRAY |
| ticket_clicked | 点击某票：flight_no/platform/price/signals | §14 | must | GRAY |
| purchase_jumped | 跳转购买：flight_no/platform/price | §14 | must | GRAY |
| memory_edited | 修改偏好：field_name | §14 | nice | GRAY |
| memory_cleared | 清空记忆 | §14 | nice | GRAY |
| fallback_triggered | 降级：reason ∈ {parse_failed, clarify_exceeded, timeout} | §14 | must | GRAY |

> 埋点是 H1–H3、转化漏斗、护栏统计的数据底座，必须上线即生效且字段齐全，否则灰度阶段无法验证假设。

---

## 3. 假设验证 H1–H6

PRD 出处：§7 MVP 假设清单。每个假设给出：验证方法 / 数据来源 / 成立标准（引用原文阈值）/ 评测时间窗。

| # | 假设 | 验证方法 | 数据来源 | 成立标准（原文阈值） | 时间窗 | 优先级 |
|---|------|---------|---------|---------------------|--------|--------|
| **H1** | 用户愿意用对话方式查票（而非表单） | 对话入口 vs 结构化表单 A/B 测试 | 埋点 search_submitted / 表单提交事件、对话完成率 | 对话完成率高于表单 **30%** | 灰度第 1 周 | P0 |
| **H2** | AI「值得买」判断能帮用户做决策 | 追踪 AI 建议采纳率（点击建议内的跳转链接） | 埋点 result_viewed → purchase_jumped（建议内链接） | 采纳率 **> 30%** | 灰度第 1 周 | P0 |
| **H3** | 用户有意愿跳转到外部平台购买 | 跳转点击率 | 埋点 result_viewed → ticket_clicked/purchase_jumped | 跳转点击率 **> 25%** | 灰度第 1 周 | P0 |
| **H4** | 偏好记忆能提升复访（「越用越懂我」） | 有偏好 vs 无偏好用户 7 日留存对比 | 留存分析（按 memories 是否为空分群） | 有偏好用户留存 **高 20%+** | 上线 30 天后 | P1 |
| **H5** | 每小时刷新缓存满足价格新鲜度预期 | 展示数据更新时间后做用户访谈 + NPS 调研 | 访谈记录、NPS 问卷、价格新鲜度投诉计数 | **NPS > 30** 且新鲜度投诉率 **< 5%** | 上线 30 天后 | P1 |
| **H6** | 「探索发现」页可作为自然流量入口 | ExplorePage 产生的查询量占比 | 埋点 search_submitted 来源归因（explore vs chat） | 探索页查询量占比 **> 20%** | v1.1 评估 | P2 |

**验证执行要点：**
- H1：A/B 分流必须等量、随机；「对话完成率」需明确定义（完成一次有效 deals 返回的查询）。
- H2 与 H3 区分：H2 看「建议内链接」采纳，H3 看整体跳转意愿；二者埋点需可区分点击来源。
- H4：分群基线必须固定（按首查后是否产生 memories），排除活跃度混淆，建议同期对照。
- H5：定量（NPS、投诉率）+ 定性（访谈），二者需同时达标。
- H6：需在 search_submitted 埋点补充「入口来源」参数，否则无法归因（当前 §14 未含来源字段，属评测前置依赖）。

---

## 4. 核心指标与护栏汇总表

### 4.1 北极星与转化漏斗（PRD §3.2）

| 指标 | MVP 目标 | v1.1 目标 | 出处 | 方法 |
|------|---------|----------|------|------|
| 月 Query-to-Purchase Clicks（QPC，北极星） | 500 次/月 | 2000 次/月 | §3.2 | GRAY |
| 查询→结果展示率 | > 80% | > 90% | §3.2 | GRAY |
| 结果→跳转购买率 | > 25% | > 35% | §3.2 | GRAY |
| AI 建议采纳率 | > 30% | > 40% | §3.2 | GRAY |
| 单次决策时间 | < 5 min | < 3 min | §3.2 | GRAY |
| 7 日留存率 | > 15% | > 25% | §3.2 | GRAY |
| 意图解析成功率 | > 90% | > 93% | §3.2 / §15 | MANUAL+GRAY |

### 4.2 护栏指标（不可牺牲的底线，PRD §3.2）

| 护栏 | 阈值 | 口径 | 出处 | 方法 |
|------|------|------|------|------|
| 深链跳转失败率 | < 5% | 跳转后未成功打开目标的比例 | §3.2 | GRAY |
| AI 建议误导率 | < 3% | 「建议买」但实际价格高于历史均价的比例 | §3.2 | GRAY+MANUAL |
| 页面 P95 加载时间 | < 3s | 端到端页面加载 | §3.2 | GRAY |

### 4.3 性能与质量指标（PRD §15）

| 指标 | 目标 | 出处 | 方法 |
|------|------|------|------|
| 意图解析成功率 | > 90%（parse_failed < 10%） | §15 | MANUAL |
| 查询→结果展示 P95 | < 3s（判断可异步追加） | §15 | GRAY |
| 判断建议生成 P95 | < 3s（异步渲染） | §15 | GRAY |
| 前端首屏加载 | < 1.5s | §15 | GRAY |
| /api/recommendations 响应 | < 500ms | §15 | GRAY |
| /api/memory 响应 | < 300ms | §15 | GRAY |

### 4.4 B 类基础评测合格标准（PRD §17.1，上线前必做）

| 维度 | 评测方法 | 合格标准 | 出处 |
|------|---------|---------|------|
| 意图解析准确率 | 30 条标注集 | ≥ 90% | §17.1 |
| 追问准确率 | 10 条多轮对话 | ≥ 90% | §17.1 |
| 值得买信号准确率 | 抽查 20 条人工核查 | ≥ 85% | §17.1 |
| 一句话建议相关性 | 人评 30 条 | ≥ 90% | §17.1 |
| 格式合规率 | 100 次调用日志自动解析 | ≥ 98% | §17.1 |

### 4.5 关键公式与口径（评测须精确核对）

| 名称 | 公式/口径 | 出处 |
|------|----------|------|
| 推荐分 recommend_score | `(hist×0.5 + pref×0.3 + bonus×0.2) × 10`，hist=`max(0,1-lowest_price/history_avg_90d)`，pref=`min(matched_count,3)/3`，bonus=`(stops==0?1:0)×0.5+(baggage_fee==0?1:0)×0.5` | §11.1 |
| 综合总价 | `price + tax + baggage_fee` | §11.1 |
| 历史低价信号 | `lowest_price < history_avg_90d × 0.85`（差值 > 15%） | §9.6 / §10.3 |
| 心理价位 | `lowest_price ≤ user.budget` | §9.4 / §9.6 |
| 避免红眼 | `dep_hour ≥ 6` 且 user 有 avoid_redeye | §9.4 / §10.2 |
| 缓存 TTL | `expires_at = crawled_at + 1h`（FLIGHT_CACHE_TTL_MINUTES=60） | §9.3 / §5.2.7 |
| session TTL | 30min 无活动失效（SESSION_TTL_MINUTES=30） | §9.9 / §5.2.7 |
| 爬取频率 | 每 1h（FLIGHT_CRAWL_INTERVAL_MINUTES=60） | §9.3 / §5.2.7 |
| 折扣/历史口径 | history_avg_90d / history_low_90d 仅真实历史数据返回，否则 null | §9.3 |

### 4.6 E2E 测试集构成（PRD §17.2，50 条，上线前）

| 类型 | 数量 | 典型 case | 出处 |
|------|------|----------|------|
| 正常主路径 | 25 | 「明天从北京去上海」「五一去三亚预算600不要红眼」 | §17.2 |
| 相对日期推算 | 8 | 「下周末」「国庆」「清明节前一天」 | §17.2 |
| 多轮追问 | 8 | 首轮缺目的地 → 补充 → 补全日期 | §17.2 |
| 边界/异常 | 6 | 空输入、纯表情、超长(>200字)、无意义 | §17.2 |
| 对抗 case | 3 | 提示注入、要求编造票价 | §17.2 |

通过判据示例（§17.2 Schema）：`intent_parsed_correctly AND deals_returned AND signals_valid`。

### 4.7 Badcase 分级与告警（PRD §17.3）

| 等级 | 定义 | 时效 | 处置 |
|------|------|------|------|
| P0 | 输出违规 / 崩溃 / 数据泄露 | 1h | 立即下线+紧急修复 |
| P1 | parse_failed > 10% / 爬虫全失败 / 缓存缺失率过高 | 24h | 热修+策略调整 |
| P2 | 单场景信号误判 / 格式偶发异常 | 1 周 | 下迭代修复 |
| P3 | advice 体验差但不影响功能 | 下季度 | 积压优化 |

LangSmith 告警阈值：parse_failed > 5%、全平台超时率 > 10%、P95 > 5s（§17.3）。

---

## 5. 评测执行清单

> 按方法分类汇总，供逐条对照打钩。✅=通过 ❌=失败 ⬜=待测。

### 5.1 可自动化（AUTO）— 上线前必须全绿

| # | 评测项 | 出处 | 状态 |
|---|--------|------|------|
| A01 | 必填槽提取 / 相对日期推算 / 约束识别 | §9.2 | ⬜ |
| A02 | 跨轮槽位合并 + null 不覆盖 + 已填不重复问 | §9.1 | ⬜ |
| A03 | clarify_count≥2 触发 show_fallback_form | §9.2.3 | ⬜ |
| A04 | 比价只读缓存 / 字段归一化 / 同航班聚合 | §9.3 | ⬜ |
| A05 | 缓存命中键 / upsert 保最新 / TTL+stale 标记 | §9.3 | ⬜ |
| A06 | 单平台超时隔离 + 全平台失败不覆盖缓存 | §9.3 / §5.2.6 | ⬜ |
| A07 | 历史价无数据返回 null（不捏造） | §9.3 | ⬜ |
| A08 | PreferenceMatch 四类规则 + boost + reasons≤3 + 无 LLM | §10.2 | ⬜ |
| A09 | 新用户空偏好跳过偏好维度（按 memories 判定） | §9.4 | ⬜ |
| A10 | 历史低价信号阈值 0.85 / advice≤20字 | §9.6 / §10.3 | ⬜ |
| A11 | is_holiday 不写入 signals | §9.6 / §10.3 | ⬜ |
| A12 | recommend_score 三项原始分 + 加权公式 + 字符串一位小数 | §11.1 | ⬜ |
| A13 | deals 三级排序（总价→boost→score） | §11.1 | ⬜ |
| A14 | 四类异步记忆学习规则（城市/价位/红眼/航司） | §9.5 | ⬜ |
| A15 | memory PATCH/DELETE 返回完整 DTO | §12.4/12.5 | ⬜ |
| A16 | recommendations 冷启动/个性化 + 4~8 张 + preview_deal 必含 | §12.6 | ⬜ |
| A17 | alerts 创建/查询 + MVP 不推送 | §9.10 | ⬜ |
| A18 | session 创建/过期/多轮上下文 + 追问响应结构 | §9.9/§12.2.1 | ⬜ |
| A19 | user_id 匿名下发 + 未知 ID 容错 | §9.8 | ⬜ |
| A20 | 熔断三态（5次→OPEN，30s→HALF_OPEN） | §5.2.6 | ⬜ |
| A21 | 偏好读取/记忆写入失败静默降级不中断 | §9.7 | ⬜ |
| A22 | 三平台深链格式 + 兜底 H5 | §11.1 | ⬜ |
| A23 | DealCardDto / SearchResponseDto / MemoryResponseDto / RecommendationsResponseDto 契约完整 | §11 | ⬜ |
| A24 | 8 个 API 接口可用 | §12.1/§16 | ⬜ |
| A25 | 图路由 + recursion_limit=20 + 工具/空响应兜底 | §5.2.2/§5.2.6 | ⬜ |
| A26 | 格式合规率 ≥ 98%（100 次调用日志解析） | §17.1 | ⬜ |
| A27 | E2E 测试集 50 条通过 | §17.2 | ⬜ |

### 5.2 需手动（MANUAL）— 上线前 B 类评测 + 体验核查

| # | 评测项 | 合格标准 | 出处 | 状态 |
|---|--------|---------|------|------|
| M01 | 意图解析准确率（30 条标注集） | ≥ 90% | §17.1 | ⬜ |
| M02 | 追问准确率（10 条多轮） | ≥ 90% | §17.1 | ⬜ |
| M03 | 值得买信号准确率（抽查 20 条） | ≥ 85% | §17.1 | ⬜ |
| M04 | 一句话建议相关性（人评 30 条） | ≥ 90% | §17.1 | ⬜ |
| M05 | 上下文感知追问文案（承接已知/不重复/≤20字） | 人评通过 | §10.1 | ⬜ |
| M06 | 对抗鲁棒性（提示注入/编造票价不被劫持） | 全部抵御 | §17.2 | ⬜ |
| M07 | MemoryPage 来源文案格式正确 + evidence 可展开 | 人评通过 | §9.4/§13.4 | ⬜ |
| M08 | 清除所有记忆确认弹窗（不可逆） | 交互正确 | §9.5 | ⬜ |
| M09 | 探索页瀑布流 + 盲盒筛选 + 快捷问题标签 | 人评通过 | §13.3 | ⬜ |
| M10 | PersonalPage MVP 纯静态符合预期 | 符合 | §13.5 | ⬜ |
| M11 | APP 未装 1.5s 降级 H5 | 行为正确 | §11.1 | ⬜ |
| M12 | function calling 模型确认（非 qwen-turbo） | 确认 | §10.0/§18.3 | ⬜ |
| M13 | 后端失败前端静默降级（memory 4 章节） | 行为正确 | §13.4 | ⬜ |
| M14 | 真实平台覆盖（携程/去哪儿/飞猪可用性） | 抽查通过 | §9.3 | ⬜ |

### 5.3 需灰度（GRAY）— 上线后埋点/留存/性能

| # | 评测项 | 阈值 | 时间窗 | 出处 | 状态 |
|---|--------|------|--------|------|------|
| G01 | 8 个埋点事件字段齐全且上报 | 全部 | 上线即生效 | §14 | ⬜ |
| G02 | 月 QPC（北极星） | ≥ 500 | 上线后月度 | §3.2 | ⬜ |
| G03 | 查询→结果展示率 | > 80% | 持续 | §3.2 | ⬜ |
| G04 | 结果→跳转购买率 | > 25% | 持续 | §3.2 | ⬜ |
| G05 | AI 建议采纳率 | > 30% | 持续 | §3.2 | ⬜ |
| G06 | 7 日留存率 | > 15% | 上线后 | §3.2 | ⬜ |
| G07 | 护栏：深链失败率 | < 5% | 持续 | §3.2 | ⬜ |
| G08 | 护栏：AI 建议误导率 | < 3% | 持续 | §3.2 | ⬜ |
| G09 | 护栏：页面 P95 加载 | < 3s | 持续 | §3.2 | ⬜ |
| G10 | 查询→结果展示 P95 | < 3s | 持续 | §15 | ⬜ |
| G11 | 判断建议生成 P95 | < 3s | 持续 | §15 | ⬜ |
| G12 | 前端首屏 / recommendations / memory 响应 | <1.5s / <500ms / <300ms | 持续 | §15 | ⬜ |
| G13 | ReAct Agent P95 / ValueJudge P95 | <2s / <3s | 持续 | §18.1/§15 | ⬜ |
| G14 | H1 对话 vs 表单 A/B | 对话完成率高 30% | 灰度第 1 周 | §7 | ⬜ |
| G15 | H2 AI 建议采纳率 | > 30% | 灰度第 1 周 | §7 | ⬜ |
| G16 | H3 跳转点击率 | > 25% | 灰度第 1 周 | §7 | ⬜ |
| G17 | H4 有/无偏好 7 日留存对比 | 高 20%+ | 上线 30 天 | §7 | ⬜ |
| G18 | H5 价格新鲜度 NPS + 投诉率 | NPS>30 且投诉<5% | 上线 30 天 | §7 | ⬜ |
| G19 | H6 探索页查询量占比 | > 20% | v1.1 | §7 | ⬜ |
| G20 | LangSmith 告警接入（parse_failed/超时/P95） | 告警生效 | 上线即生效 | §17.3 | ⬜ |

---

## 附录 A：覆盖矩阵

### A.1 PRD 功能模块覆盖

| PRD 章节 | 模块 | 本文评测节 |
|---------|------|-----------|
| §5.2.2 / §9.1 / §10 | LLM Pipeline / ReAct / State | 2.11 |
| §9.2 / §17 | 意图解析与多轮澄清 | 2.1 |
| §5.2.5 / §9.2.6 | 动态意图注册表 / Embedding 快速路 | 2.2 |
| §9.3 / §5.2.6 | 比价数据源与缓存 | 2.3 |
| §9.4 / §10.2 | 偏好匹配 PreferenceMatch | 2.4 |
| §9.6 / §10.3 | 值得买信号 ValueJudge | 2.5 |
| §11.1 | 推荐分公式 / deals 排序 | 2.6 |
| §9.5 / §11.3 / §13.4 | 记忆/偏好系统 | 2.7 |
| §12.6 / §13.3 | 探索发现页 | 2.8 |
| §9.10 | 价格监控 Alerts | 2.9 |
| §13.5 | 个人页 | 2.10 |
| §9.8 / §9.9 | user_id / session | 2.12 |
| §5.2.6 / §9.7 | 可靠性/异常处理 | 2.13 |
| §11.1 booking_url | 深链跳转 | 2.14 |
| §11 / §12 | 数据契约 DTO | 2.15 |
| §14 | 埋点 | 2.16 |

### A.2 假设覆盖

H1（§2.1+G14）、H2（§2.5+G15）、H3（§2.14+G16）、H4（§2.7+G17）、H5（§2.3+G18）、H6（§2.8+G19）—— 全部 6 个假设均在第 3 章逐条给出验证方法/数据源/成立标准。

### A.3 指标覆盖

北极星 QPC、转化漏斗 4 项、留存、决策时间、意图解析成功率（§3.2）；3 条护栏（§3.2）；6 项性能（§15）；5 项 B 类基础评测（§17.1）—— 全部汇总于第 4 章并标注阈值与出处。

### A.4 评测前置依赖与缺口提示（供执行时注意）

1. **H6 归因缺口**：§14 埋点 search_submitted 当前未含「入口来源」参数，需补充后才能统计探索页占比（G19 依赖）。
2. **工程现状差异**：据 PLAN.md，线上当前跑规则版 slot-filling，ReAct/动态意图注册表（§2.2）为半成品；评测 §2.1/§2.2 时须先确认实际接图状态，未接图项记为「N/A-未实现」而非失败。
3. **真实历史数据**：history_avg_90d/history_low_90d 依赖真实历史积累，冷启动期多为 null，G08 误导率与 A10 历史低价信号在无历史数据时按「数据有限」口径评测。
4. **PersonalPage / DELETE alerts**：§2.9–2.10 多项为 v1.1，MVP 评测不计入 must 失败。
