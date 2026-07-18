#!/bin/bash
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This collector installer only supports macOS." >&2
  exit 1
fi

ACTIVATE=false
if [[ "${1:-}" == "--activate" ]]; then
  ACTIVATE=true
elif [[ $# -gt 0 ]]; then
  echo "Usage: $0 [--activate]" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_DIR="$REPO_ROOT/.venv-collector"
PYTHON="$VENV_DIR/bin/python"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/faresniper"
ENV_FILE="$CONFIG_DIR/collector.env"
PROFILE_DIR="$HOME/.faresniper/ctrip-profile"
STATE_DIR="$HOME/.faresniper"
LOG_DIR="$STATE_DIR/logs"
PLIST_TEMPLATE="$REPO_ROOT/deploy/macos/com.faresniper.ctrip-collector.plist.template"
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$PLIST_DIR/com.faresniper.ctrip-collector.plist"

mkdir -p "$CONFIG_DIR" "$PROFILE_DIR" "$LOG_DIR" "$PLIST_DIR"
chmod 700 "$CONFIG_DIR" "$PROFILE_DIR" "$STATE_DIR" "$LOG_DIR"

python3 -m venv "$VENV_DIR"
"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install -r "$REPO_ROOT/backend/requirements-collector.txt"

if [[ ! -f "$ENV_FILE" ]]; then
  umask 077
  cat >"$ENV_FILE" <<EOF
FARESNIPER_API_URL=
CTRIP_COLLECTOR_TOKEN=
FARESNIPER_COLLECTOR_NODE_ID=
FARESNIPER_CTRIP_PROFILE="$PROFILE_DIR"
FARESNIPER_COLLECTOR_INTERVAL_SECONDS=60
CTRIP_COLLECTION_TIMEOUT_SECONDS=90
FARESNIPER_LANGSMITH_TRACING=false
LANGSMITH_API_KEY=
LANGSMITH_PROJECT=faresniper
EOF
fi
chmod 600 "$ENV_FILE"

"$PYTHON" - "$PLIST_TEMPLATE" "$PLIST_PATH" "$REPO_ROOT" "$PYTHON" "$ENV_FILE" "$LOG_DIR" <<'PY'
from pathlib import Path
from xml.sax.saxutils import escape
import shlex
import sys

template, output, repo, python, env_file, log_dir = sys.argv[1:]
text = Path(template).read_text(encoding="utf-8")
values = {
    "__REPO_ROOT_XML__": escape(repo),
    "__PYTHON_SHELL__": escape(shlex.quote(python)),
    "__ENV_FILE_SHELL__": escape(shlex.quote(env_file)),
    "__STDOUT_PATH_XML__": escape(str(Path(log_dir) / "collector.log")),
    "__STDERR_PATH_XML__": escape(str(Path(log_dir) / "collector.err.log")),
}
for marker, value in values.items():
    text = text.replace(marker, value)
Path(output).write_text(text, encoding="utf-8")
PY

plutil -lint "$PLIST_PATH"
"$PYTHON" -m backend.collector.cli --env-file "$ENV_FILE" doctor --local-only

LOGIN_COMMAND="set -a; source '$ENV_FILE'; set +a; '$PYTHON' -m backend.collector.cli --env-file '$ENV_FILE' login"

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

if [[ -z "${FARESNIPER_API_URL:-}" || -z "${CTRIP_COLLECTOR_TOKEN:-}" ]]; then
  echo
  echo "Collector files are installed but the agent was not loaded."
  echo "1. Fill FARESNIPER_API_URL and CTRIP_COLLECTOR_TOKEN in: $ENV_FILE"
  echo "2. Run the visible login command:"
  echo "   $LOGIN_COMMAND"
  echo "3. Activate the agent: $0 --activate"
  exit 0
fi

if [[ "$ACTIVATE" != true || ! -f "$PROFILE_DIR/.login-confirmed" ]]; then
  echo
  echo "Complete visible Ctrip login before loading the launch agent:"
  echo "  $LOGIN_COMMAND"
  echo "Then run: $0 --activate"
  exit 0
fi

"$PYTHON" -m backend.collector.cli --env-file "$ENV_FILE" doctor
launchctl bootout "gui/$UID" "$PLIST_PATH" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$UID" "$PLIST_PATH"
launchctl kickstart -k "gui/$UID/com.faresniper.ctrip-collector"
echo "FareSniper Ctrip collector is running."
