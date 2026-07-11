# Hive Web

[English version](README.md)

Hive Web — локальный MCP-сервер для агентов, которым нужен веб без огромных HTML-дампов в контексте. Он даёт Hermes, Claude Code, Codex, OpenCode и другим MCP-клиентам небольшой набор инструментов для поиска, извлечения страниц и управляемых браузерных сессий.

Внутри два режима работы:

```text
static-web   дешёвый поиск и извлечение страниц через SearXNG и Firecrawl
action-web   живые Playwright-сессии с компактными снимками страницы
```

Обычное исследование идёт через static-web. Если сайт требует браузер, форму или навигацию, используется action-web. Оба режима возвращают короткие структурированные ответы, а крупные данные кладут в локальные артефакты.

## Инструменты

Static tools:

- `static_web_search(query, limit=5, max_tokens=2000)`
- `static_web_extract(url, max_tokens=3000, format="markdown")`
- `static_web_get_artifact(artifact_id, name="content.md")`

Browser tools:

- `action_web_session_create(name?, headless?)`
- `action_web_navigate(session_id, url? | search_query?)`
- `action_web_snapshot(session_id, max_tokens=1200)`
- `action_web_click(session_id, ref? | selector?, confirm_sensitive=false)`
- `action_web_type(session_id, text, ref? | selector?, clear=true)`
- `action_web_press(session_id, key)`
- `action_web_close(session_id)`

## Требования

- Python 3.11+
- [`uv`](https://docs.astral.sh/uv/)
- локальный или удалённый SearXNG
- локальный или удалённый Firecrawl
- Playwright browsers для action-web

Значения по умолчанию:

```bash
SEARXNG_URL=http://localhost:8888
FIRECRAWL_API_URL=http://localhost:3002
HIVE_WEB_ARTIFACT_DIR=~/.cache/hive-web-runtime/artifacts
```

Если SearXNG и Firecrawl уже запущены по другим адресам, перед запуском MCP-сервера задайте эти переменные окружения.

## Установка

```bash
git clone https://github.com/YegorMy/hive-web.git
cd hive-web
uv sync
uv run playwright install chromium
```

Запуск unit-тестов:

```bash
HIVE_WEB_ARTIFACT_DIR=/tmp/hive-web-runtime-artifacts uv run pytest -q
```

Live smoke test через MCP. Для него Firecrawl должен быть доступен по `FIRECRAWL_API_URL`:

```bash
uv run python scripts/test-mcp-client.py
```

Ручной запуск MCP-сервера:

```bash
uv run hive-web-runtime
```

Сервер работает по MCP stdio и ждёт подключения клиента.

## Подключение к Hermes

Скрипт прописывает `hive_web` в `~/.hermes/config.yaml` и сразу проверяет подключение:

```bash
bash scripts/install-hermes-mcp.sh
```

Можно переопределить имя сервера и адреса backend-ов:

```bash
SERVER_NAME=hive_web \
SEARXNG_URL=http://localhost:8888 \
FIRECRAWL_API_URL=http://localhost:3002 \
bash scripts/install-hermes-mcp.sh
```

Ручная конфигурация Hermes:

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

После изменения MCP-конфига перезагрузите MCP в клиенте или начните новую сессию.

## Другие MCP-клиенты

Claude Code:

```bash
claude mcp add -s user hive_web -- uv run --project /absolute/path/to/hive-web hive-web-runtime
```

Codex CLI:

```bash
codex mcp add hive_web -- uv run --project /absolute/path/to/hive-web hive-web-runtime
```

OpenCode использует ту же stdio-команду в своём MCP-конфиге:

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

## Безопасность

Hive Web старается делать браузерную автоматизацию предсказуемой:

- поиск и извлечение возвращают компактный markdown или JSON, а не полный HTML по умолчанию;
- крупные данные сохраняются как артефакты и читаются по `artifact_id`;
- browser snapshot отдаёт ссылки вида `@1` и `@2`, а не весь DOM;
- `action_web_click` блокирует действия, похожие на оплату, ввод пароля, 2FA или CAPTCHA, пока клиент явно не подтвердит действие.

Это не инструмент для обхода CAPTCHA, не shopping bot и не слой для автоматизации платежей. Его назначение проще: читать, искать, извлекать страницы и аккуратно управлять браузером там, где без него нельзя.

## Разработка

```bash
uv sync
HIVE_WEB_ARTIFACT_DIR=/tmp/hive-web-runtime-artifacts uv run pytest -q
uv run python scripts/test-mcp-client.py
uv run python scripts/smoke-action-web.py
```

Если обычная директория cache недоступна в текущем окружении, используйте временную директорию для артефактов.

## Лицензия

MIT
