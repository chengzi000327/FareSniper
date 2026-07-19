#!/bin/bash
set -euo pipefail

LABEL="com.faresniper.ctrip-collector"
SERVICE_TARGET="gui/$UID/$LABEL"
PLIST_PATH="$HOME/Library/LaunchAgents/$LABEL.plist"
STATE_DIR="$HOME/.faresniper"
UNLOAD_ATTEMPTS=20
RETRY_DELAY_SECONDS=0.25

if [[ -L "$STATE_DIR" ]]; then
  echo "Refusing to uninstall through a symlinked collector state directory; nothing was removed." >&2
  exit 1
fi

agent_loaded() {
  launchctl print "$SERVICE_TARGET" >/dev/null 2>&1
}

wait_until_unloaded() {
  local attempt
  for ((attempt = 1; attempt <= UNLOAD_ATTEMPTS; attempt++)); do
    if ! agent_loaded; then
      return 0
    fi
    if ((attempt < UNLOAD_ATTEMPTS)); then
      sleep "$RETRY_DELAY_SECONDS"
    fi
  done
  return 1
}

if agent_loaded; then
  if ! launchctl bootout "$SERVICE_TARGET"; then
    echo "Could not stop the loaded FareSniper collector; nothing was removed." >&2
    exit 1
  fi
  if ! wait_until_unloaded; then
    echo "The FareSniper collector did not unload within the bounded wait; nothing was removed." >&2
    exit 1
  fi
fi
rm -f "$PLIST_PATH"

python3 - "$STATE_DIR" <<'PY'
from pathlib import Path
import shutil
import sys

state = Path(sys.argv[1]).absolute()
expected = (Path.home() / ".faresniper").absolute()
if state != expected or state.is_symlink():
    raise SystemExit("refusing unsafe collector uninstall path")

for name in ("runtime", "venv"):
    target = state / name
    if target.parent != state:
        raise SystemExit("refusing unsafe collector uninstall path")
    if target.is_symlink() or target.is_file():
        target.unlink()
    elif target.exists():
        shutil.rmtree(target)
PY

echo "FareSniper collector launch agent removed."
echo "The private runtime and virtualenv were removed."
echo "The dedicated profile, logs, and collector.env were preserved."
echo "Profile: $HOME/.faresniper/ctrip-profile"
