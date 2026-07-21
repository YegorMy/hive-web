from typing import Any, cast

import pytest

from hive_web_runtime.action_web.browser import ActionWebRuntime, BrowserSession, _playwright_proxy
from hive_web_runtime.action_web.snapshots import condense_snapshot
from hive_web_runtime.core.config import RuntimeConfig


@pytest.mark.asyncio
async def test_condense_snapshot_returns_compact_refs_not_full_html():
    raw = {
        "url": "https://tickets.example/search",
        "title": "Tickets",
        "text": "Search train tickets Pay now",
        "elements": [
            {"role": "textbox", "name": "From", "value": ""},
            {"role": "textbox", "name": "To", "value": ""},
            {"role": "button", "name": "Search"},
        ],
        "html": "<html>" + ("x" * 10000) + "</html>",
    }

    snap = condense_snapshot(raw, max_tokens=400)

    assert snap.url == "https://tickets.example/search"
    assert snap.interactives[0].ref == "@1"
    assert snap.interactives[1].name == "To"
    assert snap.tokens_estimate <= 400
    assert "html" not in snap.model_dump()


class _FakeResponse:
    status = 200


class _FakePage:
    def __init__(self, url: str = "about:blank"):
        self.url = url
        self.calls = []

    async def goto(self, url: str, wait_until: str = "domcontentloaded", timeout: int | None = None):
        self.calls.append((url, wait_until, timeout))
        self.url = url
        return _FakeResponse()


class _FakeBrowser:
    def __init__(self):
        self.context_kwargs = None

    async def new_context(self, **kwargs):
        self.context_kwargs = kwargs
        return _FakeContext()


class _FakeContext:
    async def new_page(self):
        return _FakePage()


class _FakeChromium:
    def __init__(self):
        self.launch_kwargs = None
        self.browser = _FakeBrowser()

    async def launch(self, **kwargs):
        self.launch_kwargs = kwargs
        return self.browser


class _FakePlaywright:
    def __init__(self):
        self.chromium = _FakeChromium()


@pytest.mark.asyncio
async def test_navigate_goes_to_target_url(tmp_path):
    runtime = ActionWebRuntime(config=RuntimeConfig(artifact_dir=tmp_path / "artifacts"))
    fake_page = _FakePage()
    runtime._sessions["s1"] = BrowserSession(
        session_id="s1",
        browser=object(),
        context=object(),
        page=fake_page,
        headless=True,
    )

    result = await runtime.navigate("s1", url="https://example.com/category")

    assert fake_page.calls == [("https://example.com/category", "domcontentloaded", 30000)]
    assert fake_page.url == "https://example.com/category"
    assert result == {"session_id": "s1", "url": "https://example.com/category", "status": 200}


@pytest.mark.asyncio
async def test_navigate_uses_configured_page_timeout(tmp_path):
    runtime = ActionWebRuntime(config=RuntimeConfig(artifact_dir=tmp_path / "artifacts", page_timeout_ms=1234))
    fake_page = _FakePage()
    runtime._sessions["s1"] = BrowserSession(
        session_id="s1",
        browser=object(),
        context=object(),
        page=fake_page,
        headless=True,
    )

    await runtime.navigate("s1", url="https://example.com/category")

    assert fake_page.calls == [("https://example.com/category", "domcontentloaded", 1234)]


def test_playwright_proxy_normalizes_auth_and_socks5h():
    assert _playwright_proxy("socks5h://user:p%40ss@[2001:db8::1]:19080") == {
        "server": "socks5://[2001:db8::1]:19080",
        "username": "user",
        "password": "p@ss",
    }


def test_runtime_config_reads_browser_proxy_url_file(tmp_path, monkeypatch):
    proxy_file = tmp_path / "proxy-url"
    proxy_file.write_text("http://user:pass@127.0.0.1:19081\n", encoding="utf-8")
    monkeypatch.delenv("HIVE_WEB_BROWSER_PROXY_URL", raising=False)
    monkeypatch.setenv("HIVE_WEB_BROWSER_PROXY_URL_FILE", str(proxy_file))

    config = RuntimeConfig(artifact_dir=tmp_path / "artifacts")

    assert config.browser_proxy_url == "http://user:pass@127.0.0.1:19081"


def test_runtime_config_parses_browser_args(tmp_path, monkeypatch):
    monkeypatch.setenv("HIVE_WEB_BROWSER_ARGS", "--one,--two=value")

    config = RuntimeConfig(artifact_dir=tmp_path / "artifacts")

    assert config.browser_args == ["--one", "--two=value"]


def test_runtime_config_invalid_numbers_fall_back(tmp_path, monkeypatch):
    monkeypatch.setenv("HIVE_WEB_DEFAULT_MAX_TOKENS", "nope")
    monkeypatch.setenv("HIVE_WEB_REQUEST_TIMEOUT_SECONDS", "nope")
    monkeypatch.setenv("HIVE_WEB_PAGE_TIMEOUT_MS", "nope")

    config = RuntimeConfig(artifact_dir=tmp_path / "artifacts")

    assert config.default_max_tokens == 2000
    assert config.request_timeout_seconds == 45.0
    assert config.page_timeout_ms == 30000


def test_condense_snapshot_trims_interactives_to_token_budget():
    raw = {
        "url": "https://example.com/heavy",
        "title": "Heavy",
        "text": "",
        "elements": [
            {"role": "button", "name": f"Button {i} " + ("x" * 250), "selector": f"button:nth-of-type({i})"}
            for i in range(80)
        ],
    }

    snap = condense_snapshot(raw, max_tokens=250)

    assert snap.tokens_estimate <= 250
    assert snap.truncated is True
    assert len(snap.interactives) < 80


@pytest.mark.asyncio
async def test_session_create_passes_browser_channel_proxy_and_omits_default_user_agent(tmp_path):
    runtime = ActionWebRuntime(
        config=RuntimeConfig(
            artifact_dir=tmp_path / "artifacts",
            browser_channel="chrome",
            browser_proxy_url="http://user:pass@127.0.0.1:19081",
            browser_args=["--disable-blink-features=AutomationControlled"],
            browser_locale="ru-RU",
            browser_timezone="Europe/Moscow",
            user_agent=None,
        )
    )
    fake_pw = _FakePlaywright()
    runtime._playwright = cast(Any, fake_pw)

    session = await runtime.session_create(name="s2", headless=False)

    assert session.session_id == "s2"
    assert session.headless is False
    assert fake_pw.chromium.launch_kwargs == {
        "headless": False,
        "channel": "chrome",
        "proxy": {
            "server": "http://127.0.0.1:19081",
            "username": "user",
            "password": "pass",
        },
        "args": ["--disable-blink-features=AutomationControlled"],
    }
    assert fake_pw.chromium.browser.context_kwargs == {
        "locale": "ru-RU",
        "timezone_id": "Europe/Moscow",
    }


@pytest.mark.asyncio
async def test_session_create_rejects_duplicate_session_id(tmp_path):
    runtime = ActionWebRuntime(config=RuntimeConfig(artifact_dir=tmp_path / "artifacts"))
    runtime._sessions["s2"] = BrowserSession(
        session_id="s2",
        browser=object(),
        context=object(),
        page=object(),
        headless=True,
    )

    with pytest.raises(ValueError, match="already exists"):
        await runtime.session_create(name="s2")
