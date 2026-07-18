# Mac 携程采集节点

Mac collector 使用独立 Chrome profile 登录国内携程，领取 Railway 中的航线任务，拦截 `batchSearch` 响应并上传经过作用域校验的结构化报价。Cookie、页面响应和 profile 保留在本机，不会上传到 FareSniper 或 LangSmith。

携程可能要求重新登录、CAPTCHA 或触发访问控制，因此采集不是永久可用的官方数据接口；节点需要可观察、可恢复。

## 前置条件

- 长期在线的 macOS 电脑
- Google Chrome
- Python 3.12 或更高版本
- 已部署的 FareSniper backend
- backend 中已配置 `CTRIP_COLLECTOR_TOKEN`
- 能正常访问国内携程的网络

iPad 不能运行该 launchd/Selenium 节点。安装器不会复制日常 Chrome profile，而是使用 `~/.faresniper/ctrip-profile`。

## 安装

在仓库根目录执行：

```bash
bash scripts/install_macos_collector.sh
```

安装器创建：

```text
.venv-collector/
~/.config/faresniper/collector.env
~/.faresniper/ctrip-profile/
~/.faresniper/logs/
~/Library/LaunchAgents/com.faresniper.ctrip-collector.plist
```

`collector.env` 权限为 600。填写空白项，不要把值提交到 Git：

```dotenv
FARESNIPER_API_URL=
CTRIP_COLLECTOR_TOKEN=
FARESNIPER_COLLECTOR_NODE_ID=
FARESNIPER_CTRIP_PROFILE="$HOME/.faresniper/ctrip-profile"
FARESNIPER_COLLECTOR_INTERVAL_SECONDS=60
CTRIP_COLLECTION_TIMEOUT_SECONDS=90
FARESNIPER_LANGSMITH_TRACING=false
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=faresniper
```

## Doctor 与首次登录

先验证本机依赖：

```bash
.venv-collector/bin/python -m backend.collector.cli \
  --env-file "$HOME/.config/faresniper/collector.env" \
  doctor --local-only
```

配置 backend URL 和 token 后，打开可见 Chrome 完成登录：

```bash
.venv-collector/bin/python -m backend.collector.cli \
  --env-file "$HOME/.config/faresniper/collector.env" \
  login
```

只有未来航班页和 allowlist 登录 Cookie 都验证成功后，collector 才创建 `.login-confirmed`。完成后运行完整 doctor：

```bash
.venv-collector/bin/python -m backend.collector.cli \
  --env-file "$HOME/.config/faresniper/collector.env" \
  doctor
```

## Clash Verge

携程 Chrome 只为 `ctrip.com`、`*.ctrip.com`、`ctrip.com.cn` 和 `*.ctrip.com.cn` 配置 Chrome proxy bypass，其他页面子资源继续遵循系统代理。collector 到 Railway backend 的 HTTP 请求仍可使用进程环境中的代理设置；localhost 已自动加入 `NO_PROXY`。

如果 Clash 的 TUN/增强模式仍接管所有流量，请在 Clash Verge 规则中把 `flights.ctrip.com` 和相关携程域名设为 `DIRECT`。切换外网节点不会复制或上传 profile，但出口地区频繁变化可能触发携程重新验证。

## 启动与单次检查

先手动跑一个任务：

```bash
.venv-collector/bin/python -m backend.collector.cli \
  --env-file "$HOME/.config/faresniper/collector.env" \
  once
```

确认成功后激活 launchd：

```bash
bash scripts/install_macos_collector.sh --activate
```

## 状态与日志

```bash
launchctl print "gui/$UID/com.faresniper.ctrip-collector"
tail -f "$HOME/.faresniper/logs/collector.log"
tail -f "$HOME/.faresniper/logs/collector.err.log"
```

正常节点每次循环都会发送 heartbeat。日志只包含状态和结果数量，不应出现 token、Cookie、raw response 或完整预订 URL。

## CAPTCHA 与登录恢复

出现 `captcha_required`、`login_required` 或持续 `parse_error` 时：

```bash
launchctl bootout "gui/$UID" \
  "$HOME/Library/LaunchAgents/com.faresniper.ctrip-collector.plist"
.venv-collector/bin/python -m backend.collector.cli \
  --env-file "$HOME/.config/faresniper/collector.env" \
  login
bash scripts/install_macos_collector.sh --activate
```

在可见窗口中手工完成 CAPTCHA；不要编写绕过验证码的脚本。失败会关闭浏览器会话并释放 profile lock，下一轮创建新 session。若专用 profile 已损坏，可在停止 agent 后备份并删除 `~/.faresniper/ctrip-profile`，再重新运行 `login`。

## Token 轮换

1. 在 Railway backend 生成并设置新的高熵 `CTRIP_COLLECTOR_TOKEN`。
2. 在本机 `~/.config/faresniper/collector.env` 写入相同值。
3. 重启 agent：

```bash
launchctl kickstart -k "gui/$UID/com.faresniper.ctrip-collector"
```

旧 token 会立即收到 401。不要把 token 放在命令参数、截图、日志或聊天消息中。

## 睡眠与在线要求

Mac 睡眠、关机、Chrome 更新或网络中断时，采集暂停，Railway 会把 heartbeat 标记为离线并继续展示已有快照。需要持续采集时，应接通电源并在系统设置中避免自动睡眠；唤醒后 launchd 会恢复进程，但可能需要重新登录。

## 卸载

```bash
bash scripts/uninstall_macos_collector.sh
```

卸载脚本移除 launchd agent，但故意保留配置和 `~/.faresniper/ctrip-profile`。确认不再需要登录状态后，可手工删除：

```bash
rm -rf "$HOME/.faresniper/ctrip-profile" \
  "$HOME/.faresniper/logs" \
  "$HOME/.config/faresniper/collector.env" \
  .venv-collector
```

专用 profile 始终保留在本机；删除前先确认其中没有仍需保留的携程登录状态。
