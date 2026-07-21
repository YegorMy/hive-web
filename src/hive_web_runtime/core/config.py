from __future__ import annotations

import json
import os
from pathlib import Path
from pydantic import BaseModel, Field


def _env_flag(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).lower() not in {"0", "false", "no"}


def _env_optional(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default or "")
    if value is None:
        return None
    value = value.strip()
    return value or None


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        parsed = int(value)
    except ValueError:
        return default
    return max(minimum, parsed)


def _env_float(name: str, default: float, minimum: float = 0.1) -> float:
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        parsed = float(value)
    except ValueError:
        return default
    return max(minimum, parsed)


def _browser_proxy_url() -> str | None:
    value = os.getenv("HIVE_WEB_BROWSER_PROXY_URL")
    if value and value.strip():
        return value.strip()

    path_value = os.getenv("HIVE_WEB_BROWSER_PROXY_URL_FILE")
    if not path_value:
        return None
    try:
        path = Path(path_value).expanduser()
        value = path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return value or None


def _browser_args() -> list[str]:
    value = os.getenv("HIVE_WEB_BROWSER_ARGS")
    if not value or not value.strip():
        return []
    value = value.strip()
    if value.startswith("["):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return [str(item).strip() for item in parsed if str(item).strip()]
    return [item.strip() for item in value.split(",") if item.strip()]


class RuntimeConfig(BaseModel):
    """Runtime configuration shared by static-web, action-web, and MCP."""

    searxng_url: str = Field(default_factory=lambda: os.getenv("SEARXNG_URL", "http://localhost:8888"))
    firecrawl_url: str = Field(default_factory=lambda: os.getenv("FIRECRAWL_API_URL", "http://localhost:3002"))
    artifact_dir: Path = Field(default_factory=lambda: Path(os.getenv("HIVE_WEB_ARTIFACT_DIR", str(Path.home() / ".cache/hive-web-runtime/artifacts"))))
    default_max_tokens: int = Field(default_factory=lambda: _env_int("HIVE_WEB_DEFAULT_MAX_TOKENS", 2000))
    request_timeout_seconds: float = Field(default_factory=lambda: _env_float("HIVE_WEB_REQUEST_TIMEOUT_SECONDS", 45.0))
    search_engines: str | None = Field(default_factory=lambda: _env_optional("HIVE_WEB_SEARCH_ENGINES", "bing,wikipedia,wikidata"))
    search_fallback_engines: str | None = Field(default_factory=lambda: _env_optional("HIVE_WEB_SEARCH_FALLBACK_ENGINES", "bing"))
    search_categories: str | None = Field(default_factory=lambda: _env_optional("HIVE_WEB_SEARCH_CATEGORIES"))
    search_language: str = Field(default_factory=lambda: os.getenv("HIVE_WEB_SEARCH_LANGUAGE", "auto"))
    browser_headless: bool = Field(default_factory=lambda: _env_flag("HIVE_WEB_BROWSER_HEADLESS", "true"))
    browser_channel: str | None = Field(default_factory=lambda: os.getenv("HIVE_WEB_BROWSER_CHANNEL") or None)
    browser_proxy_url: str | None = Field(default_factory=_browser_proxy_url)
    browser_args: list[str] = Field(default_factory=_browser_args)
    browser_locale: str | None = Field(default_factory=lambda: os.getenv("HIVE_WEB_BROWSER_LOCALE") or None)
    browser_timezone: str | None = Field(default_factory=lambda: os.getenv("HIVE_WEB_BROWSER_TIMEZONE") or None)
    page_timeout_ms: int = Field(default_factory=lambda: _env_int("HIVE_WEB_PAGE_TIMEOUT_MS", 30000, minimum=1000))
    user_agent: str | None = Field(default_factory=lambda: os.getenv("HIVE_WEB_USER_AGENT") or None)

    def model_post_init(self, __context: object) -> None:
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
