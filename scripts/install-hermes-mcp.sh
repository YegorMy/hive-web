#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
PROJECT_DIR="$(cd "$PROJECT_DIR" && pwd)"
SERVER_NAME="${SERVER_NAME:-hive_web}"
UV_BIN="${UV_BIN:-$(command -v uv || true)}"

if [[ -z "$UV_BIN" ]]; then
  echo "uv CLI not found. Set UV_BIN to an executable uv binary." >&2
  exit 1
fi

UV_BIN="$(cd "$(dirname "$UV_BIN")" && pwd)/$(basename "$UV_BIN")"

if ! command -v hermes >/dev/null 2>&1; then
  echo "hermes CLI not found in PATH." >&2
  echo "Manual command:" >&2
  echo "hermes mcp add ${SERVER_NAME} --command ${UV_BIN} --connect-timeout 60 --env SEARXNG_URL=http://localhost:8888 FIRECRAWL_API_URL=http://localhost:3002 HIVE_WEB_ARTIFACT_DIR=${HOME}/.cache/hive-web-runtime/artifacts HIVE_WEB_SEARCH_ENGINES=bing,wikipedia,wikidata HIVE_WEB_SEARCH_FALLBACK_ENGINES=bing --args run --project ${PROJECT_DIR} hive-web-runtime" >&2
  exit 1
fi

"$UV_BIN" sync

PROJECT_DIR="$PROJECT_DIR" UV_BIN="$UV_BIN" SERVER_NAME="$SERVER_NAME" \
  SEARXNG_URL="${SEARXNG_URL:-http://localhost:8888}" \
  FIRECRAWL_API_URL="${FIRECRAWL_API_URL:-http://localhost:3002}" \
  HIVE_WEB_ARTIFACT_DIR="${HIVE_WEB_ARTIFACT_DIR:-${HOME}/.cache/hive-web-runtime/artifacts}" \
  HIVE_WEB_SEARCH_ENGINES="${HIVE_WEB_SEARCH_ENGINES:-bing,wikipedia,wikidata}" \
  HIVE_WEB_SEARCH_FALLBACK_ENGINES="${HIVE_WEB_SEARCH_FALLBACK_ENGINES:-bing}" \
  HIVE_WEB_REQUEST_TIMEOUT_SECONDS="${HIVE_WEB_REQUEST_TIMEOUT_SECONDS:-45}" \
  HIVE_WEB_PAGE_TIMEOUT_MS="${HIVE_WEB_PAGE_TIMEOUT_MS:-30000}" \
  "$UV_BIN" run --with pyyaml python - <<'PY'
import os
from pathlib import Path

import yaml

project_dir = os.environ["PROJECT_DIR"]
uv_bin = os.environ["UV_BIN"]
server_name = os.environ["SERVER_NAME"]
artifact_default = os.path.expanduser("~/.cache/hive-web-runtime/artifacts")
artifact_dir = os.path.expanduser(os.environ.get("HIVE_WEB_ARTIFACT_DIR", artifact_default))

config_path = Path.home() / ".hermes" / "config.yaml"
config_path.parent.mkdir(parents=True, exist_ok=True)

if config_path.exists():
    with config_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
else:
    data = {}

if not isinstance(data, dict):
    data = {}

mcp_servers = data.get("mcp_servers")
if not isinstance(mcp_servers, dict):
    mcp_servers = {}
data["mcp_servers"] = mcp_servers

env = {
    "SEARXNG_URL": os.environ.get("SEARXNG_URL", "http://localhost:8888"),
    "FIRECRAWL_API_URL": os.environ.get("FIRECRAWL_API_URL", "http://localhost:3002"),
    "HIVE_WEB_ARTIFACT_DIR": artifact_dir,
    "HIVE_WEB_SEARCH_ENGINES": os.environ.get("HIVE_WEB_SEARCH_ENGINES", "bing,wikipedia,wikidata"),
    "HIVE_WEB_SEARCH_FALLBACK_ENGINES": os.environ.get("HIVE_WEB_SEARCH_FALLBACK_ENGINES", "bing"),
    "HIVE_WEB_REQUEST_TIMEOUT_SECONDS": os.environ.get("HIVE_WEB_REQUEST_TIMEOUT_SECONDS", "45"),
    "HIVE_WEB_PAGE_TIMEOUT_MS": os.environ.get("HIVE_WEB_PAGE_TIMEOUT_MS", "30000"),
}
for name in (
    "HIVE_WEB_SEARCH_CATEGORIES",
    "HIVE_WEB_SEARCH_LANGUAGE",
    "HIVE_WEB_BROWSER_HEADLESS",
    "HIVE_WEB_BROWSER_CHANNEL",
    "HIVE_WEB_BROWSER_PROXY_URL_FILE",
    "HIVE_WEB_BROWSER_ARGS",
    "HIVE_WEB_BROWSER_LOCALE",
    "HIVE_WEB_BROWSER_TIMEZONE",
    "HIVE_WEB_USER_AGENT",
):
    value = os.environ.get(name)
    if value:
        env[name] = value

mcp_servers[server_name] = {
    "command": uv_bin,
    "args": ["run", "--project", project_dir, "hive-web-runtime"],
    "env": env,
    "connect_timeout": 60,
    "enabled": True,
}

with config_path.open("w", encoding="utf-8") as f:
    yaml.safe_dump(data, f, sort_keys=False)
PY

hermes mcp test "$SERVER_NAME"
echo "run /reload-mcp or start a new chat"
