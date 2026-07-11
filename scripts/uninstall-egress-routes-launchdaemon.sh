#!/usr/bin/env bash
set -euo pipefail

LABEL="${LABEL:-com.hive-web-runtime.egress-routes}"
PLIST_PATH="/Library/LaunchDaemons/${LABEL}.plist"

if [[ "$EUID" -ne 0 ]]; then
  echo "This uninstaller must run as root:" >&2
  echo "  sudo bash $0" >&2
  exit 1
fi

launchctl bootout system "$PLIST_PATH" >/dev/null 2>&1 || true
rm -f "$PLIST_PATH"
echo "Removed ${LABEL}"
