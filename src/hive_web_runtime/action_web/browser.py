from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import unquote, urlsplit, urlunsplit

from hive_web_runtime.action_web.models import BrowserSessionInfo, BrowserSnapshot
from hive_web_runtime.action_web.snapshots import SNAPSHOT_JS, condense_snapshot
from hive_web_runtime.core.artifacts import ArtifactStore, new_artifact_id
from hive_web_runtime.core.config import RuntimeConfig
from hive_web_runtime.static_web.client import StaticWebClient

SENSITIVE_RE = re.compile(r"(pay|payment|purchase|buy now|book now|confirm booking|оплат|купить|забронировать|подтвердить|2fa|password|парол|captcha)", re.I)


@dataclass
class BrowserSession:
    session_id: str
    browser: object
    context: object
    page: object
    headless: bool
    ref_map: dict[str, str] = field(default_factory=dict)
    ref_names: dict[str, str] = field(default_factory=dict)


class ActionWebRuntime:
    """Stateful Playwright layer. It depends on static-web for search/query navigation."""

    def __init__(self, config: RuntimeConfig | None = None, static_web: StaticWebClient | None = None):
        self.config = config or RuntimeConfig()
        self.static_web = static_web or StaticWebClient(self.config)
        self.artifacts = ArtifactStore(self.config.artifact_dir)
        self._playwright = None
        self._sessions: dict[str, BrowserSession] = {}

    async def _ensure_playwright(self):
        if self._playwright is None:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
        return self._playwright

    async def session_create(self, headless: bool | None = None, name: str | None = None) -> BrowserSessionInfo:
        headless = self.config.browser_headless if headless is None else headless
        session_id = name or f"browser_{uuid.uuid4().hex[:8]}"
        if session_id in self._sessions:
            raise ValueError(f"action-web session already exists: {session_id}")
        pw = await self._ensure_playwright()
        launch_kwargs: dict[str, Any] = {"headless": headless}
        if self.config.browser_channel:
            launch_kwargs["channel"] = self.config.browser_channel
        proxy = _playwright_proxy(self.config.browser_proxy_url)
        if proxy:
            launch_kwargs["proxy"] = proxy
        if self.config.browser_args:
            launch_kwargs["args"] = self.config.browser_args
        browser = await pw.chromium.launch(**launch_kwargs)
        context_kwargs: dict[str, Any] = {}
        if self.config.user_agent:
            context_kwargs["user_agent"] = self.config.user_agent
        if self.config.browser_locale:
            context_kwargs["locale"] = self.config.browser_locale
        if self.config.browser_timezone:
            context_kwargs["timezone_id"] = self.config.browser_timezone
        context = await browser.new_context(**context_kwargs)
        page = await context.new_page()
        self._sessions[session_id] = BrowserSession(session_id, browser, context, page, headless)
        return BrowserSessionInfo(session_id=session_id, headless=headless)

    def _get(self, session_id: str) -> BrowserSession:
        if session_id not in self._sessions:
            raise KeyError(f"No action-web session: {session_id}")
        return self._sessions[session_id]

    async def navigate(self, session_id: str, url: str | None = None, search_query: str | None = None, wait_until: str = "domcontentloaded") -> dict:
        session = self._get(session_id)
        target_url = url
        if not target_url and search_query:
            result = await self.static_web.search(search_query, limit=1, max_tokens=600)
            if not result.results:
                raise ValueError(f"static-web search returned no results for: {search_query}")
            target_url = result.results[0].url
        if not target_url:
            raise ValueError("Either url or search_query is required")

        response = await session.page.goto(target_url, wait_until=wait_until, timeout=self.config.page_timeout_ms)
        return {
            "session_id": session_id,
            "url": session.page.url,
            "status": getattr(response, "status", None),
        }

    async def snapshot(self, session_id: str, max_tokens: int | None = None) -> BrowserSnapshot:
        max_tokens = max_tokens or self.config.default_max_tokens
        session = self._get(session_id)
        raw = await session.page.evaluate(SNAPSHOT_JS)
        artifact_id = new_artifact_id("browser_snapshot")
        self.artifacts.put_json(artifact_id, "raw.json", raw)
        snap = condense_snapshot(raw, max_tokens=max_tokens, session_id=session_id, artifact_id=artifact_id)
        self.artifacts.put_json(artifact_id, "snapshot.json", snap.model_dump())
        session.ref_map = {e.ref: e.selector for e in snap.interactives if e.selector}
        session.ref_names = {e.ref: f"{e.role} {e.name}" for e in snap.interactives}
        return snap

    async def click(self, session_id: str, ref: str | None = None, selector: str | None = None, confirm_sensitive: bool = False) -> dict:
        session = self._get(session_id)
        selector = selector or session.ref_map.get(ref or "")
        label = session.ref_names.get(ref or "", selector or "")
        if not confirm_sensitive and SENSITIVE_RE.search(label):
            return {"error": "SAFETY_CONFIRMATION_REQUIRED", "reason": f"Sensitive-looking target: {label}", "session_id": session_id}
        if not selector:
            raise ValueError("click requires selector or a ref from the latest snapshot")
        await session.page.locator(selector).first.click()
        return {"ok": True, "session_id": session_id, "url": session.page.url}

    async def type(self, session_id: str, text: str, ref: str | None = None, selector: str | None = None, clear: bool = True) -> dict:
        session = self._get(session_id)
        selector = selector or session.ref_map.get(ref or "")
        if not selector:
            raise ValueError("type requires selector or a ref from the latest snapshot")
        loc = session.page.locator(selector).first
        if clear:
            await loc.fill(text)
        else:
            await loc.type(text)
        return {"ok": True, "session_id": session_id, "url": session.page.url}

    async def press(self, session_id: str, key: str) -> dict:
        session = self._get(session_id)
        await session.page.keyboard.press(key)
        return {"ok": True, "session_id": session_id, "url": session.page.url}

    async def close(self, session_id: str) -> dict:
        session = self._sessions.pop(session_id, None)
        if not session:
            return {"ok": True, "session_id": session_id, "already_closed": True}
        await session.context.close()
        await session.browser.close()
        return {"ok": True, "session_id": session_id}

    async def shutdown(self) -> None:
        for sid in list(self._sessions):
            await self.close(sid)
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None


def _playwright_proxy(proxy_url: str | None) -> dict[str, str] | None:
    if not proxy_url:
        return None
    parsed = urlsplit(proxy_url)
    if not parsed.scheme or not parsed.hostname:
        return {"server": proxy_url}
    scheme = "socks5" if parsed.scheme.lower() == "socks5h" else parsed.scheme
    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    netloc = host if parsed.port is None else f"{host}:{parsed.port}"
    proxy: dict[str, str] = {"server": urlunsplit((scheme, netloc, "", "", ""))}
    if parsed.username:
        proxy["username"] = unquote(parsed.username)
    if parsed.password:
        proxy["password"] = unquote(parsed.password)
    return proxy
