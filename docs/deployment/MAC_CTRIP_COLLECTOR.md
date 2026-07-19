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
export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.faresniper/config}"
INSTALLER_PATH="$(pwd -P)/scripts/install_macos_collector.sh"
bash "$INSTALLER_PATH"
```

当前采集节点使用 `~/.faresniper/config`，因为本机 `~/.config` 不可写。
若使用其他自定义目录，请在后续登录、doctor、激活和恢复命令中继续导出
同一个 `XDG_CONFIG_HOME`，不要在激活时切回另一个配置目录。

安装器创建：

```text
~/.faresniper/venv/
~/.faresniper/runtime/
${XDG_CONFIG_HOME:-$HOME/.config}/faresniper/collector.env
~/.faresniper/ctrip-profile/
~/.faresniper/logs/
~/Library/LaunchAgents/com.faresniper.ctrip-collector.plist
```

`venv`、collector 所需的最小 Python 源码副本和 launchd 工作目录都位于
`~/.faresniper`。安装完成后，LaunchAgent 不再读取仓库或 `~/Documents`。
runtime 使用显式文件 allowlist 构建，不会复制 `backend/.env`、测试、
`__pycache__`、`.pyc`、工具缓存、密钥文件或其他应用源码；重复安装会
先在 `~/.faresniper` 的暂存路径构建 venv、runtime 和 plist，并通过
local/full doctor 后才停止旧 agent、交换资源和启动新版本。交换或启动
失败时会恢复旧资源并重新启动原服务，同时保留 `collector.env`、日志和
携程 profile。

agent 已加载时，不带 `--activate` 的安装会直接拒绝且不会改动运行资源；
升级运行中的节点必须沿用上述 XDG 导出和绝对 `INSTALLER_PATH` 执行
`bash "$INSTALLER_PATH" --activate`。

`collector.env` 权限为 600。填写空白项，不要把值提交到 Git：

```dotenv
FARESNIPER_API_URL=
CTRIP_COLLECTOR_TOKEN=
FARESNIPER_COLLECTOR_NODE_ID=
FARESNIPER_CTRIP_PROFILE=
FARESNIPER_CTRIP_HEADLESS=false
FARESNIPER_COLLECTOR_INTERVAL_SECONDS=60
CTRIP_COLLECTION_TIMEOUT_SECONDS=90
FARESNIPER_LANGSMITH_TRACING=false
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=faresniper
```

新配置中的 `FARESNIPER_CTRIP_PROFILE` 故意留空，CLI 会使用精确默认目录
`~/.faresniper/ctrip-profile`。已有配置中的显式自定义路径不会被安装器改写。

Mac 安装器显式使用可见浏览器采集，因为携程可能阻止 headless
会话。CLI 在未配置 `FARESNIPER_CTRIP_HEADLESS` 时仍默认为 `true`，
以保持原有行为；本机采集应保留安装器写入的 `false`。该变量只接受
常见布尔值，例如 `true`、`false`、`1` 和 `0`。

## Doctor 与首次登录

先验证本机依赖：

```bash
COLLECTOR_ENV_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/faresniper/collector.env"
(
  cd "$HOME/.faresniper/runtime"
  PYTHONDONTWRITEBYTECODE=1 \
    "$HOME/.faresniper/venv/bin/python" -m backend.collector.cli \
    --env-file "$COLLECTOR_ENV_FILE" \
    doctor --local-only
)
```

配置 backend URL 和 token 后，打开可见 Chrome 完成登录：

```bash
COLLECTOR_ENV_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/faresniper/collector.env"
(
  cd "$HOME/.faresniper/runtime"
  PYTHONDONTWRITEBYTECODE=1 \
    "$HOME/.faresniper/venv/bin/python" -m backend.collector.cli \
    --env-file "$COLLECTOR_ENV_FILE" \
    login
)
```

只有未来航班页和 allowlist 登录 Cookie 都验证成功后，collector 才创建 `.login-confirmed`。完成后运行完整 doctor：

```bash
COLLECTOR_ENV_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/faresniper/collector.env"
(
  cd "$HOME/.faresniper/runtime"
  PYTHONDONTWRITEBYTECODE=1 \
    "$HOME/.faresniper/venv/bin/python" -m backend.collector.cli \
    --env-file "$COLLECTOR_ENV_FILE" \
    doctor
)
```

## Clash Verge

携程 Chrome 只为 `ctrip.com`、`*.ctrip.com`、`ctrip.com.cn` 和 `*.ctrip.com.cn` 配置 Chrome proxy bypass，其他页面子资源继续遵循系统代理。collector 到 Railway backend 的 HTTP 请求不读取 `HTTP_PROXY`/`HTTPS_PROXY`，并使用 macOS 系统信任库校验证书，避免 Clash 环境代理的证书链影响报价上传；localhost 已自动加入 `NO_PROXY`。

如果 Clash 的 TUN/增强模式仍接管所有流量，请在 Clash Verge 规则中把 `flights.ctrip.com` 和相关携程域名设为 `DIRECT`。切换外网节点不会复制或上传 profile，但出口地区频繁变化可能触发携程重新验证。

## 启动与单次检查

先手动跑一个任务：

```bash
COLLECTOR_ENV_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/faresniper/collector.env"
(
  cd "$HOME/.faresniper/runtime"
  PYTHONDONTWRITEBYTECODE=1 \
    "$HOME/.faresniper/venv/bin/python" -m backend.collector.cli \
    --env-file "$COLLECTOR_ENV_FILE" \
    once
)
```

确认成功后激活 launchd：

```bash
export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.faresniper/config}"
INSTALLER_PATH="$(pwd -P)/scripts/install_macos_collector.sh"
bash "$INSTALLER_PATH" --activate
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
export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$HOME/.faresniper/config}"
launchctl bootout "gui/$UID/com.faresniper.ctrip-collector"
COLLECTOR_ENV_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/faresniper/collector.env"
(
  cd "$HOME/.faresniper/runtime"
  PYTHONDONTWRITEBYTECODE=1 \
    "$HOME/.faresniper/venv/bin/python" -m backend.collector.cli \
    --env-file "$COLLECTOR_ENV_FILE" \
    login
)
INSTALLER_PATH="$(pwd -P)/scripts/install_macos_collector.sh"
bash "$INSTALLER_PATH" --activate
```

在可见窗口中手工完成 CAPTCHA；不要编写绕过验证码的脚本。失败会关闭浏览器会话并释放 profile lock，下一轮创建新 session。若专用 profile 已损坏，可在停止 agent 后备份并删除 `~/.faresniper/ctrip-profile`，再重新运行 `login`。

## Token 轮换

1. 在 Railway backend 生成并设置新的高熵 `CTRIP_COLLECTOR_TOKEN`。
2. 在本机 `${XDG_CONFIG_HOME:-$HOME/.config}/faresniper/collector.env` 写入相同值。
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

卸载脚本会移除 launchd agent、私有 runtime 和 venv，但故意保留日志、
配置和 `~/.faresniper/ctrip-profile`。若已加载 agent 无法停止，卸载会在
删除任何文件前中止。确认不再需要登录状态后，可手工删除：

```bash
COLLECTOR_ENV_FILE="${XDG_CONFIG_HOME:-$HOME/.config}/faresniper/collector.env"
rm -rf "$HOME/.faresniper/ctrip-profile" \
  "$HOME/.faresniper/logs" \
  "$COLLECTOR_ENV_FILE"
```

旧版安装器可能在仓库留下已被 `.gitignore` 排除的 `.venv-collector/`，
确认没有旧进程使用后可从仓库手工移除。专用 profile 始终保留在本机；
删除前先确认其中没有仍需保留的携程登录状态。
