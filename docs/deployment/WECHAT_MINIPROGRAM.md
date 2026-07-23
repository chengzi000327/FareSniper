# FareSniper 微信小程序

## 目标

微信小程序不是一套独立业务。它复用 FareSniper 的搜索、聚合、用户记忆和
价格监控 API，只新增微信身份与微信订阅消息通道：

```text
微信小程序
  ├─ wx.login -> POST /api/auth/wechat/session -> OpenID 绑定 -> FareSniper JWT
  ├─ 搜索/探索/记忆 -> 现有 FareSniper API
  └─ 创建监控 -> 用户授权一次性订阅消息
                         |
Railway Worker（15 分钟）
  ├─ 同航线去重
  ├─ 主动刷新 FlyAI / SerpAPI，并读取携程快照
  ├─ 比较完整总价与目标价
  └─ Notification Outbox -> 微信订阅消息 -> 监控详情页

Mac 携程节点（每小时）
  └─ 领取 active alert 高优先级任务 -> 上传国内携程快照
```

“实时监控”在当前实现中是最长约 15 分钟一次的轮询，不是秒级行情。飞猪和
国际来源由监控 Worker 主动查询；携程受本地采集节点在线状态影响，按最近成功
快照参与判断并每小时请求刷新。

## 小程序页面

- `探索`：读取个性化推荐，可直接带着推荐问法进入对话。
- `对话`：确认出发地、目的地、未来日期和预算后搜索，展示票价、机建燃油、
  行李额、完整总价和实际销售平台。
- `监控`：展示目标总价、最新报价、来源、检查时间和通知状态，支持暂停与恢复。
- `我的`：展示从真实查询和用户确认中形成的偏好记忆。
- `监控详情`：微信通知落地页，可查看命中价格并取消监控。

## 微信公众平台配置

1. 注册并认证微信小程序，取得 AppID 和 AppSecret。
2. 在“开发管理 -> 开发设置 -> 服务器域名”中加入 Railway 后端 HTTPS 域名：
   - `request 合法域名`：`https://backend-production-8a88.up.railway.app`
   - `downloadFile 合法域名`：`https://frontend-production-9c2c.up.railway.app`
   - 生产环境必须开启域名校验，不要保留开发工具中的“不校验合法域名”。
3. 在“订阅消息”中选择一条价格提醒模板，模板至少包含：
   - 航线：`thing`
   - 出发日期：`date`
   - 当前价格：`amount`
   - 提醒说明：`thing`
4. 记录模板 ID 和四个真实字段键。字段键以微信后台为准，不一定是示例中的
   `thing1/date2/amount3/thing4`。
5. 仓库和正式微信工程都必须保留当前正式 AppID：
   `wx8dfe97d9e078549a`。同步脚本会校验 AppID，不匹配时直接停止。

项目已将 `libVersion` 固定为 `widelyUsed`，避免开发者工具自动选择灰度或
本地异常的基础库版本。不要把它改为 `trial`；如需定位兼容问题，可在开发者
工具“详情 -> 本地设置”中临时切换版本，但提交前应恢复为 `widelyUsed`。

AppSecret 只能配置在 Railway 后端，绝不能写进小程序代码、构建变量或 Git。

## Railway 变量

后端服务和 Worker 服务使用同一组微信配置：

```dotenv
WECHAT_MINI_APP_ID=
WECHAT_MINI_APP_SECRET=
WECHAT_PRICE_ALERT_TEMPLATE_ID=
WECHAT_PRICE_ALERT_ROUTE_FIELD=thing1
WECHAT_PRICE_ALERT_DATE_FIELD=date2
WECHAT_PRICE_ALERT_PRICE_FIELD=amount3
WECHAT_PRICE_ALERT_REMARK_FIELD=thing4
WECHAT_API_BASE_URL=https://api.weixin.qq.com
WECHAT_REQUEST_TIMEOUT_SECONDS=10
```

变量归属：

- Backend 需要 AppID/AppSecret，用于 `code2session` 和签发 FareSniper JWT。
- Worker 需要 AppID/AppSecret、模板 ID 和字段键，用于获取
  `access_token` 并发送订阅消息。
- Frontend 不需要微信密钥。
- 小程序只需要公开的后端 URL、模板 ID 和静态资源 URL。

部署代码后先执行：

```bash
alembic -c backend/alembic.ini upgrade head
```

迁移会统一旧 `price_alerts` 与当前 `alerts`，并创建：

- `wechat_accounts`：FareSniper 用户与小程序 OpenID 的绑定。
- `alert_subscriptions`：每条监控的一次性微信授权。
- `notification_outbox`：幂等通知、租约、重试次数和投递状态。

## 小程序构建变量

复制 `miniprogram/.env.example` 为 `miniprogram/.env`：

```dotenv
TARO_APP_API_BASE_URL=https://backend-production-8a88.up.railway.app
TARO_APP_ASSET_BASE_URL=https://frontend-production-9c2c.up.railway.app
TARO_APP_WECHAT_PRICE_ALERT_TEMPLATE_ID=
TARO_APP_USE_MOCK=false
```

`TARO_APP_WECHAT_PRICE_ALERT_TEMPLATE_ID` 必须与 Railway 的
`WECHAT_PRICE_ALERT_TEMPLATE_ID` 完全一致。开发 UI 时可把
`TARO_APP_USE_MOCK` 设为 `true`；提审包必须为 `false`。

## 构建与预览

```bash
npm --prefix miniprogram install
npm --prefix miniprogram run typecheck
npm --prefix miniprogram run build:weapp
```

微信开发者工具选择“导入项目”，项目目录选 `miniprogram/`，构建目录由
`project.config.json` 指向 `dist/`。

当前正式微信工程位于 `/Users/chengzi/WeChatProjects/faresniper`。开发完成后
使用受保护的同步脚本构建生产包并复制到该工程：

```bash
cd miniprogram
TARO_APP_API_BASE_URL=https://backend-production-8a88.up.railway.app \
  ./scripts/sync-formal-project.sh \
  /Users/chengzi/WeChatProjects/faresniper production
```

只做本地界面验收时可以将最后一个参数改为 `mock`。生产同步如果没有传入
`TARO_APP_API_BASE_URL` 会直接失败，避免误把 Mock 包或空后端地址上传审核。

至少完成以下真机验收：

1. 首次打开后 `wx.login` 成功，后端不返回 503。
2. 输入完整航线和未来日期，结果卡能显示真实平台、完整总价和费用字段。
3. 点击“监控这个价格”，修改目标价并允许订阅消息。
4. Railway `alerts`、`alert_subscriptions` 中出现对应记录。
5. 把测试目标价设到当前价以上，等待 Worker 检查后收到微信服务通知。
6. 点击通知进入对应监控详情，`notification_outbox` 状态为 `sent`。
7. 拒绝订阅时监控仍能创建，但界面应显示未启用微信通知。
8. 在监控列表再次点击“开启微信提醒”，授权后原监控应更新为已订阅。

## 通知可靠性

- 每次命中使用唯一 `event_key`，重复 Worker 执行不会重复入队。
- Dispatcher 每分钟领取待发送记录并设置租约，避免多个 Worker 重复投递。
- 网络错误指数退避重试；模板错误、无效 OpenID、用户拒绝等永久错误会停止重试。
- 微信一次性订阅消息发送后即消费。再次激活同一监控不等于重新获得微信授权；
  需要用户再次点击并授权一条新的提醒。
- 消息只包含航线、日期、命中价格和短说明，不发送用户原始对话或模型上下文。

## 发布前清单

- AppID、AppSecret、模板 ID 和模板字段已在 Railway 正确配置。
- 后端域名已完成 HTTPS、备案要求和微信 request 域名配置。
- Railway Backend 与 Worker 已运行同一个 migration head。
- Mac 携程节点在线；离线时界面明确展示最近快照时间，不伪装实时。
- 关闭 `TARO_APP_USE_MOCK`，将 `project.config.json` 替换为正式 AppID。
- 在 iOS 与 Android 微信真机完成登录、搜索、授权、拒绝、通知落地五条链路。
