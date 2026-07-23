#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MINI_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
TARGET_ROOT="${1:-/Users/chengzi/WeChatProjects/faresniper}"
MODE="${2:-production}"

if [[ ! -f "${TARGET_ROOT}/project.config.json" ]]; then
  echo "未找到正式小程序工程：${TARGET_ROOT}" >&2
  exit 1
fi

APP_ID="$(node -p "require('${TARGET_ROOT}/project.config.json').appid || ''")"
if [[ "${APP_ID}" != "wx8dfe97d9e078549a" ]]; then
  echo "目标工程 AppID 不匹配，已停止同步：${APP_ID}" >&2
  exit 1
fi

cd "${MINI_ROOT}"

if [[ "${MODE}" == "mock" ]]; then
  TARO_APP_USE_MOCK=true npm run build:weapp
else
  if [[ -z "${TARO_APP_API_BASE_URL:-}" ]]; then
    echo "生产同步必须提供 TARO_APP_API_BASE_URL。" >&2
    echo "仅做界面验收时可使用：$0 '${TARGET_ROOT}' mock" >&2
    exit 1
  fi
  TARO_APP_USE_MOCK=false npm run build:weapp
fi

mkdir -p "${TARGET_ROOT}/miniprogram"
rsync -a --delete "${MINI_ROOT}/dist/" "${TARGET_ROOT}/miniprogram/"

echo "已同步到 ${TARGET_ROOT}"
echo "AppID: ${APP_ID}"
echo "模式: ${MODE}"
