#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
UV_BIN="${UV_BIN:-$(command -v uv)}"
TARGET_URL="${HIVE_WEB_EGRESS_URL:-https://www.ozon.ru}"
CONFIG_PATH="${CONFIG_PATH:-$HOME/.config/hive-web-runtime/egress-routes.json}"
STATE_PATH="${STATE_PATH:-$HOME/.cache/hive-web-runtime/egress-routes-state.json}"

if [[ -z "${UV_BIN}" ]]; then
  echo "uv CLI not found. Install uv first." >&2
  exit 1
fi

"$UV_BIN" run --project "$PROJECT_DIR" hive-web-egress-routes \
  --config "$CONFIG_PATH" \
  --state "$STATE_PATH" \
  ensure --force --url "$TARGET_URL"
