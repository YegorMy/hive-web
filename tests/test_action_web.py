import pytest

from hive_web_runtime.action_web.browser import ActionWebRuntime, BrowserSession
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

    async def goto(self, url: str, wait_until: str = "domcontentloaded"):
        self.calls.append((url, wait_until))
        self.url = url
        return _FakeResponse()


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

    assert fake_page.calls == [("https://example.com/category", "domcontentloaded")]
    assert fake_page.url == "https://example.com/category"
    assert result == {"session_id": "s1", "url": "https://example.com/category", "status": 200}
