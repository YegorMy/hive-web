#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
UV_BIN="${UV_BIN:-$(command -v uv || true)}"
LABEL="${LABEL:-com.hive-web-runtime.egress-routes}"
PLIST_PATH="/Library/LaunchDaemons/${LABEL}.plist"
INTERVAL_SECONDS="${INTERVAL_SECONDS:-1800}"
TARGET_URL="${TARGET_URL:-https://www.ozon.ru}"
TARGET_USER="${TARGET_USER:-${SUDO_USER:-$(logname 2>/dev/null || whoami)}}"
TARGET_HOME="${TARGET_HOME:-$(dscl . -read "/Users/${TARGET_USER}" NFSHomeDirectory 2>/dev/null | awk '{print $2}')}"
CONFIG_PATH="${CONFIG_PATH:-${TARGET_HOME}/.config/hive-web-runtime/egress-routes.json}"
STATE_PATH="${STATE_PATH:-${TARGET_HOME}/.cache/hive-web-runtime/egress-routes-state.json}"

if [[ -z "$UV_BIN" ]]; then
  echo "uv CLI not found. Set UV_BIN=/absolute/path/to/uv" >&2
  exit 1
fi

if [[ "$EUID" -ne 0 ]]; then
  echo "This installer writes $PLIST_PATH and must run as root:" >&2
  echo "  sudo PROJECT_DIR='$PROJECT_DIR' UV_BIN='$UV_BIN' TARGET_USER='$TARGET_USER' bash $0" >&2
  exit 1
fi

if [[ -z "$TARGET_HOME" ]]; then
  echo "Could not resolve target home for user '$TARGET_USER'. Set TARGET_HOME explicitly." >&2
  exit 1
fi

mkdir -p "$(dirname "$CONFIG_PATH")" "$(dirname "$STATE_PATH")"

cat > "$PLIST_PATH" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>${LABEL}</string>
  <key>ProgramArguments</key>
  <array>
    <string>${UV_BIN}</string>
    <string>run</string>
    <string>--project</string>
    <string>${PROJECT_DIR}</string>
    <string>hive-web-egress-routes</string>
    <string>--config</string>
    <string>${CONFIG_PATH}</string>
    <string>--state</string>
    <string>${STATE_PATH}</string>
    <string>ensure</string>
    <string>--force</string>
    <string>--url</string>
    <string>${TARGET_URL}</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>StartInterval</key>
  <integer>${INTERVAL_SECONDS}</integer>
  <key>StandardOutPath</key>
  <string>/var/log/${LABEL}.out.log</string>
  <key>StandardErrorPath</key>
  <string>/var/log/${LABEL}.err.log</string>
</dict>
</plist>
PLIST

chown root:wheel "$PLIST_PATH"
chmod 644 "$PLIST_PATH"
launchctl bootout system "$PLIST_PATH" >/dev/null 2>&1 || true
launchctl bootstrap system "$PLIST_PATH"
launchctl kickstart -k "system/${LABEL}"

echo "Installed ${LABEL} at ${PLIST_PATH}"
echo "Refresh interval: ${INTERVAL_SECONDS}s"
echo "Target URL: ${TARGET_URL}"
echo "Config: ${CONFIG_PATH}"
echo "State: ${STATE_PATH}"
