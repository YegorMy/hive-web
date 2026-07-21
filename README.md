# Hive Web

[Русская версия](readme_rus.md)

Hive Web is a local MCP server for agents that need web access without flooding the model with raw pages. It gives Hermes, Claude Code, Codex, OpenCode, and other MCP clients a small set of tools for search, page extraction, and controlled browser sessions.

The server is built around two paths:

```text
static-web   cheap search and page extraction through SearXNG and Firecrawl
action-web   live Playwright sessions with compact snapshots and safe actions
```

Static tools handle normal research. Action tools are for sites that need a browser, forms, or navigation. Both return compact, structured data and store larger payloads as local artifacts.

## Naming

The project is called **Hive Web**. The GitHub repository is `hive-web`.

The Python package and executable are named `hive-web-runtime` because they run the local MCP server. MCP clients usually register that server as `hive_web`.

```text
GitHub repository   hive-web
Python package      hive-web-runtime
CLI command         hive-web-runtime
MCP server name     hive_web
Python module       hive_web_runtime
```

## Tools

Static tools:

- `static_web_search(query, limit=5, max_tokens=2000)`
- `static_web_extract(url, max_tokens=3000, format="markdown")`
- `static_web_get_artifact(artifact_id, name?)`

Browser tools:

- `action_web_session_create(name?, headless?)`
- `action_web_navigate(session_id, url? | search_query?)`
- `action_web_snapshot(session_id, max_tokens=1200)`
- `action_web_click(session_id, ref? | selector?, confirm_sensitive=false)`
- `action_web_type(session_id, text, ref? | selector?, clear=true)`
- `action_web_press(session_id, key)`
- `action_web_close(session_id)`

## Requirements

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/)
- Local or remote SearXNG endpoint
- Local or remote Firecrawl endpoint
- Playwright browsers for action-web sessions

Default endpoints:

```bash
SEARXNG_URL=http://localhost:8888
FIRECRAWL_API_URL=http://localhost:3002
HIVE_WEB_ARTIFACT_DIR=~/.cache/hive-web-runtime/artifacts
HIVE_WEB_SEARCH_ENGINES=bing,wikipedia,wikidata
HIVE_WEB_SEARCH_FALLBACK_ENGINES=bing
HIVE_WEB_REQUEST_TIMEOUT_SECONDS=45
```

`static_web_search` pins SearXNG to reliable engines by default instead of letting blocked/CAPTCHA-heavy public engines silently return empty JSON. Override `HIVE_WEB_SEARCH_ENGINES` if your SearXNG instance has a better engine mix. Search responses include `warnings` from SearXNG `unresponsive_engines`, so CAPTCHA/rate-limit/backend failures are visible to the caller instead of looking like "the web has no results".

Action-web browser options:

```bash
HIVE_WEB_BROWSER_HEADLESS=false          # default true
HIVE_WEB_BROWSER_CHANNEL=chrome         # optional: use installed Google Chrome instead of bundled Chromium
HIVE_WEB_BROWSER_PROXY_URL_FILE=~/.config/hive-web-runtime/browser-proxy-url
HIVE_WEB_BROWSER_ARGS=--disable-blink-features=AutomationControlled
HIVE_WEB_BROWSER_LOCALE=ru-RU
HIVE_WEB_BROWSER_TIMEZONE=Europe/Moscow
HIVE_WEB_PAGE_TIMEOUT_MS=30000
# or HIVE_WEB_BROWSER_PROXY_URL=http://user:password@host:port
```

Prefer `HIVE_WEB_BROWSER_PROXY_URL_FILE` for authenticated proxies so secrets stay out of MCP YAML config. The file should be user-readable only, for example mode `0600`.

If you already run SearXNG and Firecrawl somewhere else, set those environment variables before starting the MCP server.

## Running the backend services

Hive Web is an MCP runtime, not a bundled search/scrape stack. Start SearXNG and Firecrawl first, then start or register the MCP server.

If you use the companion local Docker stack on macOS, the normal flow is:

```bash
cd ~/workspace/hermes/hermes-local-web-stack
./scripts/start.sh          # docker compose up -d and endpoint checks
./scripts/status.sh         # verifies SearXNG search and Firecrawl /v1/scrape
./scripts/ensure-running.sh # idempotent readiness/repair check used by autostart
```

Expected healthy status:

```text
SearXNG: 10 results
Firecrawl scrape: HTTP 200 ... markdown chars
```

`scripts/status.sh` should check a real Firecrawl scrape, not just that port `3002` answers. A root HTTP 200 only proves the API process is listening; `static_web_extract` requires `/v1/scrape` to work.

For a generic setup, any SearXNG instance that serves JSON search and any Firecrawl-compatible API work:

```bash
export SEARXNG_URL=http://localhost:8888
export FIRECRAWL_API_URL=http://localhost:3002
```

## Install

```bash
git clone https://github.com/YegorMy/hive-web.git
cd hive-web
uv run playwright install chromium
bash scripts/install-hermes-mcp.sh
```

The installer runs `uv sync`, writes a `hive_web` entry into `~/.hermes/config.yaml`, and tests the MCP connection. The Playwright install step is needed for `action_web_*` browser tools; `static_web_*` tools only need SearXNG and Firecrawl.

The installer also persists the search engine and timeout options shown above. If you set browser options such as `HIVE_WEB_BROWSER_CHANNEL`, `HIVE_WEB_BROWSER_PROXY_URL_FILE`, locale, timezone, or `HIVE_WEB_BROWSER_ARGS` before running it, those safe runtime options are copied into the Hermes MCP entry too. Secrets should stay in files or client secret stores, not in public examples.

After changing MCP config, reload MCP in your client or start a new session.

```text
/reload-mcp
```

Manual server start, mostly useful for debugging:

```bash
uv run hive-web-runtime
```

The server speaks MCP over stdio, so it waits for an MCP client.

## Quick local smoke test

With SearXNG and Firecrawl already healthy:

```bash
cd /path/to/hive-web
uv run pytest -q
hermes mcp test hive_web
uv run python scripts/test-mcp-client.py
uv run python scripts/smoke-action-web.py
```

`scripts/test-mcp-client.py` initializes the MCP server over stdio, lists tools, and calls `static_web_extract` against `https://example.com`. It fails if the MCP tool returns an error, so a green run means Firecrawl extraction actually worked.

## Development checks

Run the unit tests:

```bash
HIVE_WEB_ARTIFACT_DIR=/tmp/hive-web-runtime-artifacts uv run pytest -q
```

Run a live MCP smoke test. This requires Firecrawl to be reachable at `FIRECRAWL_API_URL`:

```bash
uv run python scripts/test-mcp-client.py
```

For live browser changes, also run:

```bash
uv run python scripts/smoke-action-web.py
```

## Hermes setup

If you skipped the install script above, run it from the cloned repository:

```bash
bash scripts/install-hermes-mcp.sh
```

You can override the server name and endpoints:

```bash
SERVER_NAME=hive_web \
SEARXNG_URL=http://localhost:8888 \
FIRECRAWL_API_URL=http://localhost:3002 \
bash scripts/install-hermes-mcp.sh
```

Manual Hermes config:

```yaml
mcp_servers:
  hive_web:
    command: /absolute/path/to/uv
    args: ["run", "--project", "/absolute/path/to/hive-web", "hive-web-runtime"]
    env:
      SEARXNG_URL: "http://localhost:8888"
      FIRECRAWL_API_URL: "http://localhost:3002"
      HIVE_WEB_ARTIFACT_DIR: "/absolute/path/to/artifacts"
      HIVE_WEB_SEARCH_ENGINES: "bing,wikipedia,wikidata"
      HIVE_WEB_SEARCH_FALLBACK_ENGINES: "bing"
      HIVE_WEB_REQUEST_TIMEOUT_SECONDS: "45"
      HIVE_WEB_PAGE_TIMEOUT_MS: "30000"
    connect_timeout: 60
    enabled: true
```

After changing MCP config, reload MCP in the client or start a new session.

## Other MCP clients

Claude Code:

```bash
claude mcp add -s user hive_web -- uv run --project /absolute/path/to/hive-web hive-web-runtime
```

Codex CLI:

```bash
codex mcp add hive_web -- uv run --project /absolute/path/to/hive-web hive-web-runtime
```

OpenCode uses the same stdio command in its MCP config:

```json
{
  "mcp": {
    "hive_web": {
      "command": "uv",
      "args": ["run", "--project", "/absolute/path/to/hive-web", "hive-web-runtime"]
    }
  }
}
```

## Safety model

Hive Web tries to keep browser automation boring and predictable:

- Search and extraction return compact markdown or structured JSON, not full raw HTML by default.
- Larger payloads go into the artifact store and can be fetched by `artifact_id`.
- `static_web_get_artifact` picks the most useful artifact file automatically when `name` is omitted (`content.md`, `snapshot.json`, `results.json`, then `raw.json`).
- Browser snapshots expose refs like `@1` and `@2` instead of dumping the full DOM.
- `action_web_click` blocks payment, password, 2FA, and CAPTCHA-looking targets unless the caller explicitly confirms the action.

## Reliability behavior

- Static search and extraction use configurable request timeouts (`HIVE_WEB_REQUEST_TIMEOUT_SECONDS`).
- Action-web navigation uses `HIVE_WEB_PAGE_TIMEOUT_MS` instead of waiting forever on stuck pages.
- Duplicate named browser sessions are rejected instead of silently overwriting and leaking an old browser context.
- Firecrawl error payloads are surfaced as explicit errors and their raw response is saved as an artifact for debugging.
- Browser snapshots are trimmed to the requested token budget, including interactives, while the raw snapshot remains available in the artifact store.

This is not a CAPTCHA bypass tool, a shopping bot, or a payment automation layer. Treat it as read/search/extract plus careful browser control.

## Network routing

Hive Web does not mutate system routes or install routing helpers. For browser sessions that need a special exit path, configure an action-web browser proxy with `HIVE_WEB_BROWSER_PROXY_URL_FILE` or `HIVE_WEB_BROWSER_PROXY_URL`; static-web search/extract remains routed through its SearXNG/Firecrawl backends.

## Development

```bash
uv sync
HIVE_WEB_ARTIFACT_DIR=/tmp/hive-web-runtime-artifacts uv run pytest -q
uv run python scripts/test-mcp-client.py
uv run python scripts/smoke-action-web.py
```

Use a temporary artifact directory for tests if your normal cache directory is not writable in the current environment.

## License

MIT
