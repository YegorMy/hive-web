#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
UV_BIN="${UV_BIN:-$(command -v uv || true)}"
TARGET_USER="${TARGET_USER:-${SUDO_USER:-$(logname 2>/dev/null || whoami)}}"
TARGET_HOME="${TARGET_HOME:-$(dscl . -read "/Users/${TARGET_USER}" NFSHomeDirectory 2>/dev/null | awk '{print $2}')}"
CONFIG_PATH="${CONFIG_PATH:-${TARGET_HOME}/.config/hive-web-runtime/egress-routes.json}"
STATE_PATH="${STATE_PATH:-${TARGET_HOME}/.cache/hive-web-runtime/egress-routes-state.json}"
TARGET_URL="${TARGET_URL:-https://www.ozon.ru}"
INTERVAL_SECONDS="${INTERVAL_SECONDS:-1800}"
LABEL="${LABEL:-com.hive-web-runtime.egress-routes.ozon}"

if [[ -z "$UV_BIN" ]]; then
  echo "uv CLI not found. Set UV_BIN=/absolute/path/to/uv" >&2
  exit 1
fi

if [[ -z "$TARGET_HOME" ]]; then
  echo "Could not resolve target home for user '$TARGET_USER'. Set TARGET_HOME explicitly." >&2
  exit 1
fi

mkdir -p "$(dirname "$CONFIG_PATH")" "$(dirname "$STATE_PATH")"

CONFIG_PATH="$CONFIG_PATH" python3 - <<'PY'
import json
import os
from pathlib import Path

path = Path(os.environ["CONFIG_PATH"]).expanduser()
path.parent.mkdir(parents=True, exist_ok=True)

rule = {
    "name": "ozon-direct",
    "enabled": True,
    "domains": ["ozon.ru", "www.ozon.ru", ".ozon.ru"],
    "resolve_hosts": ["ozon.ru", "www.ozon.ru"],
    "gateway": "auto",
    "interface": "auto",
    "strict": False,
}

def load_config() -> dict:
    if not path.exists():
        return {"enabled": True, "refresh_interval_seconds": 3600, "rules": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    if not isinstance(data, dict):
        data = {}
    data.setdefault("enabled", True)
    data.setdefault("refresh_interval_seconds", 3600)
    rules = data.setdefault("rules", [])
    if not isinstance(rules, list):
        data["rules"] = []
    return data

config = load_config()
rules = config["rules"]
for index, existing in enumerate(rules):
    if isinstance(existing, dict) and existing.get("name") == "ozon-direct":
        rules[index] = {**existing, **rule}
        break
else:
    rules.append(rule)

path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"Updated Ozon egress rule: {path}")
PY

if [[ "$EUID" -ne 0 ]]; then
  echo "Installing LaunchDaemon requires root. Re-running through sudo..." >&2
  exec sudo \
    PROJECT_DIR="$PROJECT_DIR" \
    UV_BIN="$UV_BIN" \
    TARGET_USER="$TARGET_USER" \
    TARGET_HOME="$TARGET_HOME" \
    CONFIG_PATH="$CONFIG_PATH" \
    STATE_PATH="$STATE_PATH" \
    TARGET_URL="$TARGET_URL" \
    INTERVAL_SECONDS="$INTERVAL_SECONDS" \
    LABEL="$LABEL" \
    bash "$0"
fi

PROJECT_DIR="$PROJECT_DIR" \
UV_BIN="$UV_BIN" \
TARGET_USER="$TARGET_USER" \
TARGET_HOME="$TARGET_HOME" \
CONFIG_PATH="$CONFIG_PATH" \
STATE_PATH="$STATE_PATH" \
TARGET_URL="$TARGET_URL" \
INTERVAL_SECONDS="$INTERVAL_SECONDS" \
LABEL="$LABEL" \
bash "$PROJECT_DIR/scripts/install-egress-routes-launchdaemon.sh"

"$UV_BIN" run --project "$PROJECT_DIR" hive-web-egress-routes \
  --config "$CONFIG_PATH" \
  --state "$STATE_PATH" \
  status
