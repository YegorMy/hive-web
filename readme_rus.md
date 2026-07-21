# Hive Web

[English version](README.md)

Hive Web — локальный MCP-сервер для агентов, которым нужен веб без огромных HTML-дампов в контексте. Он даёт Hermes, Claude Code, Codex, OpenCode и другим MCP-клиентам небольшой набор инструментов для поиска, извлечения страниц и управляемых браузерных сессий.

Внутри два режима работы:

```text
static-web   дешёвый поиск и извлечение страниц через SearXNG и Firecrawl
action-web   живые Playwright-сессии с компактными снимками страницы
```

Обычное исследование идёт через static-web. Если сайт требует браузер, форму или навигацию, используется action-web. Оба режима возвращают короткие структурированные ответы, а крупные данные кладут в локальные артефакты.

## Имена

Проект называется **Hive Web**. Репозиторий на GitHub называется `hive-web`.

Python-пакет и исполняемая команда называются `hive-web-runtime`, потому что это локальный runtime/MCP-сервер. В MCP-клиентах сервер обычно регистрируется как `hive_web`.

```text
GitHub repository   hive-web
Python package      hive-web-runtime
CLI command         hive-web-runtime
MCP server name     hive_web
Python module       hive_web_runtime
```

## Инструменты

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
HIVE_WEB_SEARCH_ENGINES=bing,wikipedia,wikidata
HIVE_WEB_SEARCH_FALLBACK_ENGINES=bing
HIVE_WEB_REQUEST_TIMEOUT_SECONDS=45
```

`static_web_search` по умолчанию закрепляет SearXNG за более надёжными engines, а не даёт CAPTCHA-heavy public engines молча возвращать пустой JSON. Если у вашего SearXNG другой рабочий набор engines, переопределите `HIVE_WEB_SEARCH_ENGINES`. Search-ответы включают `warnings` из SearXNG `unresponsive_engines`, поэтому CAPTCHA/rate-limit/backend failures видны клиенту, а не выглядят как «в интернете ничего нет».

Настройки action-web браузера:

```bash
HIVE_WEB_BROWSER_HEADLESS=false          # по умолчанию true
HIVE_WEB_BROWSER_CHANNEL=chrome         # опционально: установленный Google Chrome вместо bundled Chromium
HIVE_WEB_BROWSER_PROXY_URL_FILE=~/.config/hive-web-runtime/browser-proxy-url
HIVE_WEB_BROWSER_ARGS=--disable-blink-features=AutomationControlled
HIVE_WEB_BROWSER_LOCALE=ru-RU
HIVE_WEB_BROWSER_TIMEZONE=Europe/Moscow
HIVE_WEB_PAGE_TIMEOUT_MS=30000
# или HIVE_WEB_BROWSER_PROXY_URL=http://user:password@host:port
```

Для authenticated proxy лучше использовать `HIVE_WEB_BROWSER_PROXY_URL_FILE`, чтобы не хранить секрет в MCP YAML-конфиге. Файл должен быть доступен только пользователю, например с правами `0600`.

Если SearXNG и Firecrawl уже запущены по другим адресам, перед запуском MCP-сервера задайте эти переменные окружения.

## Установка

```bash
git clone https://github.com/YegorMy/hive-web.git
cd hive-web
uv run playwright install chromium
bash scripts/install-hermes-mcp.sh
```

Скрипт установки запускает `uv sync`, прописывает `hive_web` в `~/.hermes/config.yaml` и проверяет MCP-подключение. Шаг с Playwright нужен для браузерных инструментов `action_web_*`; для `static_web_*` достаточно SearXNG и Firecrawl.

Installer также сохраняет search engine и timeout options, показанные выше. Если перед запуском задать browser options вроде `HIVE_WEB_BROWSER_CHANNEL`, `HIVE_WEB_BROWSER_PROXY_URL_FILE`, locale, timezone или `HIVE_WEB_BROWSER_ARGS`, эти безопасные runtime-настройки тоже попадут в Hermes MCP entry. Секреты лучше хранить в файлах или secret store клиента, а не в публичных примерах.

После изменения MCP-конфига перезагрузите MCP в клиенте или начните новую сессию.

```text
/reload-mcp
```

Ручной запуск сервера, обычно только для отладки:

```bash
uv run hive-web-runtime
```

Сервер работает по MCP stdio и ждёт подключения клиента.

## Проверки для разработки

Запуск unit-тестов:

```bash
HIVE_WEB_ARTIFACT_DIR=/tmp/hive-web-runtime-artifacts uv run pytest -q
```

Live smoke test через MCP. Для него Firecrawl должен быть доступен по `FIRECRAWL_API_URL`:

```bash
uv run python scripts/test-mcp-client.py
```

## Подключение к Hermes

Если вы не запускали installer выше, выполните его из клонированного репозитория:

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
      HIVE_WEB_SEARCH_ENGINES: "bing,wikipedia,wikidata"
      HIVE_WEB_SEARCH_FALLBACK_ENGINES: "bing"
      HIVE_WEB_REQUEST_TIMEOUT_SECONDS: "45"
      HIVE_WEB_PAGE_TIMEOUT_MS: "30000"
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
- `static_web_get_artifact` сам выбирает самый полезный файл артефакта, если `name` не указан (`content.md`, `snapshot.json`, `results.json`, затем `raw.json`);
- browser snapshot отдаёт ссылки вида `@1` и `@2`, а не весь DOM;
- `action_web_click` блокирует действия, похожие на оплату, ввод пароля, 2FA или CAPTCHA, пока клиент явно не подтвердит действие.

## Надёжность

- Static search и extraction используют настраиваемый request timeout (`HIVE_WEB_REQUEST_TIMEOUT_SECONDS`).
- Action-web navigation использует `HIVE_WEB_PAGE_TIMEOUT_MS`, а не ждёт бесконечно зависшие страницы.
- Повторное создание browser session с тем же именем явно отклоняется, а не перетирает старую сессию с утечкой browser context.
- Firecrawl error payloads поднимаются как явные ошибки, а raw response сохраняется как artifact для отладки.
- Browser snapshots режутся под requested token budget, включая interactives, при этом raw snapshot остаётся доступен в artifact store.

Это не инструмент для обхода CAPTCHA, не shopping bot и не слой для автоматизации платежей. Его назначение проще: читать, искать, извлекать страницы и аккуратно управлять браузером там, где без него нельзя.

## Сетевая маршрутизация

Hive Web не меняет системные маршруты и не устанавливает routing helpers. Если браузерной сессии нужен специальный exit path, настройте action-web browser proxy через `HIVE_WEB_BROWSER_PROXY_URL_FILE` или `HIVE_WEB_BROWSER_PROXY_URL`; static-web search/extract продолжает ходить через свои SearXNG/Firecrawl backend-ы.

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
