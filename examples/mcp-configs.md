# MCP config examples

## Stdio command

```bash
uv run --project /absolute/path/to/hive-web hive-web-runtime
```

## Hermes install script

```bash
cd /absolute/path/to/hive-web
bash scripts/install-hermes-mcp.sh
```

Optional overrides:

```bash
SERVER_NAME=hive_web \
SEARXNG_URL=http://localhost:8888 \
FIRECRAWL_API_URL=http://localhost:3002 \
bash scripts/install-hermes-mcp.sh
```

## Hermes config shape

```yaml
mcp_servers:
  hive_web:
    command: /absolute/path/to/uv
    args: ["run", "--project", "/absolute/path/to/hive-web", "hive-web-runtime"]
    env:
      SEARXNG_URL: "http://localhost:8888"
      FIRECRAWL_API_URL: "http://localhost:3002"
      HIVE_WEB_ARTIFACT_DIR: "/absolute/path/to/artifacts"
    connect_timeout: 60
    enabled: true
```

## Claude Code

```bash
claude mcp add -s user hive_web -- uv run --project /absolute/path/to/hive-web hive-web-runtime
```

## Codex CLI

```bash
codex mcp add hive_web -- uv run --project /absolute/path/to/hive-web hive-web-runtime
```

## OpenCode

Use the same command and arguments in OpenCode's MCP config:

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
