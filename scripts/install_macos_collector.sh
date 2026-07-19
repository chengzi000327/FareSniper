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
INSTALLER_PATH="$SCRIPT_DIR/$(basename "$0")"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
STATE_DIR="$HOME/.faresniper"
VENV_DIR="$STATE_DIR/venv"
PYTHON="$VENV_DIR/bin/python"
RUNTIME_DIR="$STATE_DIR/runtime"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/faresniper"
ENV_FILE="$CONFIG_DIR/collector.env"
PROFILE_DIR="$STATE_DIR/ctrip-profile"
LOG_DIR="$STATE_DIR/logs"
PLIST_TEMPLATE="$REPO_ROOT/deploy/macos/com.faresniper.ctrip-collector.plist.template"
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$PLIST_DIR/com.faresniper.ctrip-collector.plist"
LABEL="com.faresniper.ctrip-collector"
SERVICE_DOMAIN="gui/$UID"
SERVICE_TARGET="$SERVICE_DOMAIN/$LABEL"

RUNTIME_SOURCE_FILES=(
  backend/__init__.py
  backend/config.py
  backend/collector/__init__.py
  backend/collector/browser.py
  backend/collector/cli.py
  backend/collector/client.py
  backend/collector/runner.py
  backend/application/__init__.py
  backend/application/contracts/__init__.py
  backend/application/contracts/collector.py
  backend/application/contracts/flight_provider.py
  backend/application/services/__init__.py
  backend/application/services/airport_catalog.py
  backend/application/services/domestic_fees.py
  backend/application/services/flight_dates.py
  backend/application/services/flight_query.py
  backend/infrastructure/__init__.py
  backend/infrastructure/flight_data/__init__.py
  backend/infrastructure/flight_data/ctrip_parser.py
  backend/schemas/__init__.py
  backend/schemas/collector.py
  backend/utils/__init__.py
  backend/utils/airport_codes.py
  backend/data/china_airports.json
)

agent_loaded() {
  launchctl print "$SERVICE_TARGET" >/dev/null 2>&1
}

LAUNCHCTL_UNLOAD_ATTEMPTS=20
LAUNCHCTL_BOOTSTRAP_ATTEMPTS=4
LAUNCHCTL_RETRY_DELAY_SECONDS=0.25

wait_until_unloaded() {
  local attempt
  for ((attempt = 1; attempt <= LAUNCHCTL_UNLOAD_ATTEMPTS; attempt++)); do
    if ! agent_loaded; then
      return 0
    fi
    if ((attempt < LAUNCHCTL_UNLOAD_ATTEMPTS)); then
      sleep "$LAUNCHCTL_RETRY_DELAY_SECONDS"
    fi
  done
  return 1
}

bootstrap_service() {
  local attempt
  for ((attempt = 1; attempt <= LAUNCHCTL_BOOTSTRAP_ATTEMPTS; attempt++)); do
    if launchctl bootstrap "$SERVICE_DOMAIN" "$PLIST_PATH"; then
      return 0
    fi
    if agent_loaded; then
      return 0
    fi
    if ((attempt < LAUNCHCTL_BOOTSTRAP_ATTEMPTS)); then
      sleep "$LAUNCHCTL_RETRY_DELAY_SECONDS"
    fi
  done
  return 1
}

WAS_LOADED=false
if agent_loaded; then
  WAS_LOADED=true
  if [[ "$ACTIVATE" != true ]]; then
    echo "The FareSniper collector is loaded; rerun with --activate for an atomic upgrade." >&2
    exit 3
  fi
fi

if [[ -L "$STATE_DIR" ]]; then
  echo "Refusing to install through a symlinked collector state directory." >&2
  exit 1
fi
mkdir -p "$CONFIG_DIR" "$PROFILE_DIR" "$LOG_DIR" "$PLIST_DIR"
chmod 700 "$CONFIG_DIR" "$PROFILE_DIR" "$STATE_DIR" "$LOG_DIR"

VENV_STAGE=""
RUNTIME_STAGE=""
PLIST_STAGE=""
VENV_BACKUP="$STATE_DIR/.venv-rollback.$$"
RUNTIME_BACKUP="$STATE_DIR/.runtime-rollback.$$"
PLIST_BACKUP="$STATE_DIR/.plist-rollback.$$"
SWAPPED=false
SERVICE_STOPPED=false
COMMITTED=false
SHOULD_START=false

manage_resources() {
  local action=$1
  python3 - "$action" "$STATE_DIR" \
    "$VENV_STAGE" "$RUNTIME_STAGE" "$PLIST_STAGE" \
    "$VENV_BACKUP" "$RUNTIME_BACKUP" "$PLIST_BACKUP" \
    "$VENV_DIR" "$RUNTIME_DIR" "$PLIST_PATH" <<'PY'
from pathlib import Path
import shutil
import sys

(
    action,
    state_raw,
    venv_stage_raw,
    runtime_stage_raw,
    plist_stage_raw,
    venv_backup_raw,
    runtime_backup_raw,
    plist_backup_raw,
    venv_target_raw,
    runtime_target_raw,
    plist_target_raw,
) = sys.argv[1:]

state = Path(state_raw).absolute()
expected_state = (Path.home() / ".faresniper").absolute()
if state != expected_state or state.is_symlink():
    raise SystemExit("refusing unsafe collector state path")


def present(path: Path) -> bool:
    return path.is_symlink() or path.exists()


def state_path(raw: str, prefix: str) -> Path:
    path = Path(raw).absolute()
    if path.parent != state or not path.name.startswith(prefix):
        raise SystemExit("refusing unsafe collector transaction path")
    return path


stages = []
for raw, prefix in (
    (venv_stage_raw, ".venv-stage."),
    (runtime_stage_raw, ".runtime-stage."),
    (plist_stage_raw, ".plist-stage."),
):
    if raw:
        stages.append(state_path(raw, prefix))


def remove(path: Path, allowed: set[Path]) -> None:
    if path not in allowed:
        raise SystemExit("refusing unsafe collector deletion")
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


if action == "cleanup":
    allowed = set(stages)
    for stage in stages:
        remove(stage, allowed)
    raise SystemExit(0)

if len(stages) != 3:
    raise SystemExit("collector transaction is missing a staging path")

backups = [
    state_path(venv_backup_raw, ".venv-rollback."),
    state_path(runtime_backup_raw, ".runtime-rollback."),
    state_path(plist_backup_raw, ".plist-rollback."),
]
targets = [
    Path(venv_target_raw).absolute(),
    Path(runtime_target_raw).absolute(),
    Path(plist_target_raw).absolute(),
]
expected_targets = [
    state / "venv",
    state / "runtime",
    (Path.home() / "Library/LaunchAgents/com.faresniper.ctrip-collector.plist").absolute(),
]
if targets != expected_targets:
    raise SystemExit("refusing unsafe collector target path")

pairs = list(zip(targets, backups, strict=True))
allowed_targets = set(targets)
allowed_backups = set(backups)


def restore() -> None:
    for target in reversed(targets):
        remove(target, allowed_targets)
    for target, backup in reversed(pairs):
        if present(backup):
            backup.rename(target)


if action == "swap":
    if any(present(backup) for backup in backups):
        raise SystemExit("collector rollback path already exists")
    backed_up = []
    installed = []
    try:
        for target, backup in pairs:
            if present(target):
                target.rename(backup)
                backed_up.append((target, backup))
        for stage, target in zip(stages, targets, strict=True):
            stage.rename(target)
            installed.append(target)
    except BaseException:
        for target in reversed(installed):
            remove(target, allowed_targets)
        for target, backup in reversed(backed_up):
            backup.rename(target)
        raise
elif action == "rollback":
    restore()
elif action == "commit":
    for backup in backups:
        remove(backup, allowed_backups)
else:
    raise SystemExit("unknown collector transaction action")
PY
}

cleanup_on_exit() {
  local status=$?
  local rollback_ok=true
  trap - EXIT
  set +e

  if [[ "$COMMITTED" != true ]]; then
    if [[ "$SWAPPED" == true ]]; then
      if [[ "$SHOULD_START" == true ]]; then
        if agent_loaded; then
          if ! launchctl bootout "$SERVICE_TARGET" >/dev/null 2>&1 || \
            ! wait_until_unloaded; then
            rollback_ok=false
            echo "The failed upgraded collector is still active; new targets and old backups were preserved for manual recovery." >&2
          fi
        fi
      fi
      if [[ "$rollback_ok" == true ]] && ! manage_resources rollback; then
        rollback_ok=false
        echo "Collector rollback failed; managed backups were preserved for recovery." >&2
      fi
    fi
    if [[ "$SERVICE_STOPPED" == true && "$rollback_ok" == true ]]; then
      if ! bootstrap_service >/dev/null 2>&1 || \
        ! launchctl kickstart -k "$SERVICE_TARGET" >/dev/null 2>&1; then
        echo "The previous collector files were restored, but its service could not be restarted." >&2
      fi
    fi
  fi

  if [[ "$rollback_ok" == true ]]; then
    manage_resources cleanup >/dev/null 2>&1 || true
  fi
  exit "$status"
}
trap cleanup_on_exit EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if [[ ! -f "$ENV_FILE" ]]; then
  umask 077
  cat >"$ENV_FILE" <<EOF
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
EOF
fi
if ! grep -Eq '^[[:space:]]*(export[[:space:]]+)?FARESNIPER_CTRIP_HEADLESS=' "$ENV_FILE"; then
  printf '\nFARESNIPER_CTRIP_HEADLESS=false\n' >>"$ENV_FILE"
fi
chmod 600 "$ENV_FILE"

VENV_STAGE="$(mktemp -d "$STATE_DIR/.venv-stage.XXXXXX")"
STAGE_PYTHON="$VENV_STAGE/bin/python"
python3 -m venv "$VENV_STAGE"
"$STAGE_PYTHON" -m pip install --upgrade pip
"$STAGE_PYTHON" -m pip install -r "$REPO_ROOT/backend/requirements-collector.txt"

RUNTIME_STAGE="$(mktemp -d "$STATE_DIR/.runtime-stage.XXXXXX")"
for relative_path in "${RUNTIME_SOURCE_FILES[@]}"; do
  source_path="$REPO_ROOT/$relative_path"
  destination_path="$RUNTIME_STAGE/$relative_path"
  if [[ ! -f "$source_path" || -L "$source_path" ]]; then
    echo "Collector runtime source is missing or unsafe." >&2
    exit 1
  fi
  mkdir -p "$(dirname "$destination_path")"
  cp -p "$source_path" "$destination_path"
done
chmod -R go-rwx "$RUNTIME_STAGE"

assert_runtime_safe() {
  if find "$RUNTIME_STAGE" \
    \( -type d \( -name tests -o -name __pycache__ -o -name .pytest_cache \
      -o -name .mypy_cache -o -name .ruff_cache -o -name .cache \) \
    -o -type f \( -name '.env' -o -name '.env.*' -o -name '*.py[co]' \
      -o -name '*.pem' -o -name '*.key' -o -name '*.p12' -o -name '*.pfx' \) \) \
    -print -quit | grep -q .; then
    echo "Collector runtime contains a forbidden file." >&2
    exit 1
  fi
}
assert_runtime_safe

PLIST_STAGE="$(mktemp "$STATE_DIR/.plist-stage.XXXXXX")"
python3 - "$PLIST_TEMPLATE" "$PLIST_STAGE" "$RUNTIME_DIR" "$PYTHON" "$ENV_FILE" "$LOG_DIR" <<'PY'
from pathlib import Path
from xml.sax.saxutils import escape
import sys

template, output, runtime, python, env_file, log_dir = sys.argv[1:]
text = Path(template).read_text(encoding="utf-8")
values = {
    "__RUNTIME_DIR_XML__": escape(runtime),
    "__PYTHON_XML__": escape(python),
    "__ENV_FILE_XML__": escape(env_file),
    "__STDOUT_PATH_XML__": escape(str(Path(log_dir) / "collector.log")),
    "__STDERR_PATH_XML__": escape(str(Path(log_dir) / "collector.err.log")),
}
for marker, value in values.items():
    text = text.replace(marker, value)
Path(output).write_text(text, encoding="utf-8")
PY
plutil -lint "$PLIST_STAGE"

(cd "$RUNTIME_STAGE" && \
  PYTHONDONTWRITEBYTECODE=1 \
  "$STAGE_PYTHON" -m backend.collector.cli --env-file "$ENV_FILE" doctor --local-only)

set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

CONFIGURED=false
LOGGED_IN=false
if [[ -n "${FARESNIPER_API_URL:-}" && -n "${CTRIP_COLLECTOR_TOKEN:-}" ]]; then
  CONFIGURED=true
fi
if [[ -f "$PROFILE_DIR/.login-confirmed" ]]; then
  LOGGED_IN=true
fi
if [[ "$CONFIGURED" == true && "$LOGGED_IN" == true ]]; then
  (cd "$RUNTIME_STAGE" && \
    PYTHONDONTWRITEBYTECODE=1 \
    "$STAGE_PYTHON" -m backend.collector.cli --env-file "$ENV_FILE" doctor)
fi
assert_runtime_safe

if [[ "$WAS_LOADED" == true && \
  ("$CONFIGURED" != true || "$LOGGED_IN" != true) ]]; then
  echo "The loaded collector cannot be upgraded until configuration and login checks pass." >&2
  exit 1
fi

if [[ "$ACTIVATE" == true && "$CONFIGURED" == true && "$LOGGED_IN" == true ]]; then
  SHOULD_START=true
fi

if [[ "$WAS_LOADED" == true ]]; then
  if ! agent_loaded; then
    echo "Collector service state changed during validation; no resources were replaced." >&2
    exit 1
  fi
  if ! launchctl bootout "$SERVICE_TARGET"; then
    echo "Could not stop the loaded collector; no resources were replaced." >&2
    exit 1
  fi
  SERVICE_STOPPED=true
  if ! wait_until_unloaded; then
    echo "The loaded collector did not unload within the bounded wait; no resources were replaced." >&2
    exit 1
  fi
elif agent_loaded; then
  echo "A collector was loaded during installation; no resources were replaced." >&2
  exit 1
fi

manage_resources swap
SWAPPED=true

if [[ "$SHOULD_START" == true ]]; then
  if ! bootstrap_service; then
    echo "Could not bootstrap the upgraded collector; restoring the previous install." >&2
    exit 1
  fi
  if ! launchctl kickstart -k "$SERVICE_TARGET"; then
    echo "Could not start the upgraded collector; restoring the previous install." >&2
    exit 1
  fi
fi

COMMITTED=true
if ! manage_resources commit; then
  echo "The upgrade succeeded, but one or more old managed backups could not be removed." >&2
fi

printf -v RUNTIME_SHELL '%q' "$RUNTIME_DIR"
printf -v ENV_SHELL '%q' "$ENV_FILE"
printf -v PYTHON_SHELL '%q' "$PYTHON"
printf -v INSTALLER_SHELL '%q' "$INSTALLER_PATH"
LOGIN_COMMAND="(cd $RUNTIME_SHELL && set -a && source $ENV_SHELL && set +a && PYTHONDONTWRITEBYTECODE=1 $PYTHON_SHELL -m backend.collector.cli --env-file $ENV_SHELL login)"

if [[ "$CONFIGURED" != true ]]; then
  echo
  echo "Collector files are installed but the agent was not loaded."
  echo "1. Fill FARESNIPER_API_URL and CTRIP_COLLECTOR_TOKEN in: $ENV_FILE"
  echo "2. Run the visible login command:"
  echo "   $LOGIN_COMMAND"
  echo "3. Activate the agent: $INSTALLER_SHELL --activate"
elif [[ "$LOGGED_IN" != true ]]; then
  echo
  echo "Complete visible Ctrip login before loading the launch agent:"
  echo "  $LOGIN_COMMAND"
  echo "Then run: $INSTALLER_SHELL --activate"
elif [[ "$SHOULD_START" != true ]]; then
  echo "Collector files are validated and installed."
  echo "Activate the agent with: $INSTALLER_SHELL --activate"
else
  echo "FareSniper Ctrip collector is running."
fi
