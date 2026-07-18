#!/bin/bash
set -euo pipefail

PLIST_PATH="$HOME/Library/LaunchAgents/com.faresniper.ctrip-collector.plist"
launchctl bootout "gui/$UID" "$PLIST_PATH" >/dev/null 2>&1 || true
rm -f "$PLIST_PATH"

echo "FareSniper collector launch agent removed."
echo "The dedicated profile and collector.env were preserved."
echo "Profile: $HOME/.faresniper/ctrip-profile"

