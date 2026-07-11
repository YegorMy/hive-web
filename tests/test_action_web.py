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


class _StubRouteManager:
    def __init__(self):
        self.calls = []

    def ensure_for_url(self, url: str, force: bool = False):
        self.calls.append((url, force))
        return {"matched": True, "host": "ozon.ru", "rules": []}


@pytest.mark.asyncio
async def test_navigate_runs_egress_route_gate_before_goto(tmp_path):
    route_manager = _StubRouteManager()
    runtime = ActionWebRuntime(
        config=RuntimeConfig(
            artifact_dir=tmp_path / "artifacts",
            egress_routes_config_path=tmp_path / "egress-routes.json",
            egress_routes_state_path=tmp_path / "egress-routes-state.json",
        ),
        egress_routes=route_manager,
    )
    fake_page = _FakePage()
    runtime._sessions["s1"] = BrowserSession(
        session_id="s1",
        browser=object(),
        context=object(),
        page=fake_page,
        headless=True,
    )

    result = await runtime.navigate("s1", url="https://www.ozon.ru/category")

    assert route_manager.calls == [("https://www.ozon.ru/category", False)]
    assert fake_page.url == "https://www.ozon.ru/category"
    assert result["egress_route"]["matched"] is True
