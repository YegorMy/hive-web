# Architecture

```text
web-core
  config, token counting, artifact store

static-web
  depends on web-core
  talks to SearXNG and Firecrawl
  stateless, cheap, cacheable

action-web
  depends on web-core + static-web
  owns Playwright sessions
  returns compact interactive snapshots
  safety-gates sensitive actions

mcp-server
  thin adapter over static-web and action-web
```

Dependency rule:

```text
static-web -> web-core
action-web -> static-web + web-core
mcp-server -> static-web + action-web
```

No `hive-crawler` module exists; Hive's cheap page search is `static-web`.
