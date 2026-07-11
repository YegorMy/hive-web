import pytest

from hive_web_runtime.static_web.client import StaticWebClient
from hive_web_runtime.static_web.models import SearchResult
from hive_web_runtime.core.config import RuntimeConfig


class StubTransport:
    def __init__(self, manager=None):
        self.manager = manager

    async def search(self, query: str, limit: int):
        assert query == "hermes agent"
        assert limit == 2
        return {
            "results": [
                {"title": "Hermes", "url": "https://example.com/hermes", "content": "Agent docs"},
                {"title": "Nous", "url": "https://example.com/nous", "content": "Research"},
            ]
        }

    async def extract(self, url: str, formats: list[str]):
        if self.manager:
            self.manager.ensure_for_url(url)
        assert formats == ["markdown"]
        return {
            "success": True,
            "data": {"title": "Example", "markdown": "# Hello\nWorld", "url": url},
        }


@pytest.mark.asyncio
async def test_static_search_normalizes_results_and_token_counts(tmp_path):
    config = RuntimeConfig(
        artifact_dir=tmp_path / "artifacts",
        egress_routes_config_path=tmp_path / "egress-routes.json",
        egress_routes_state_path=tmp_path / "egress-routes-state.json",
    )
    client = StaticWebClient(config, transport=StubTransport())

    result = await client.search("hermes agent", limit=2, max_tokens=500)

    assert result.query == "hermes agent"
    assert len(result.results) == 2
    assert isinstance(result.results[0], SearchResult)
    assert result.results[0].title == "Hermes"
    assert result.results[0].snippet == "Agent docs"
    assert result.tokens_estimate > 0
    assert result.artifact_id.startswith("search_")


@pytest.mark.asyncio
async def test_static_extract_normalizes_firecrawl_markdown(tmp_path):
    config = RuntimeConfig(
        artifact_dir=tmp_path / "artifacts",
        egress_routes_config_path=tmp_path / "egress-routes.json",
        egress_routes_state_path=tmp_path / "egress-routes-state.json",
    )
    client = StaticWebClient(config, transport=StubTransport())

    page = await client.extract("https://example.com", max_tokens=1000)

    assert page.url == "https://example.com"
    assert page.title == "Example"
    assert page.markdown == "# Hello\nWorld"
    assert page.tokens_estimate > 0
    assert page.artifact_id.startswith("extract_")


class _StubEgressManager:
    def __init__(self):
        self.calls = []

    def ensure_for_url(self, url: str, force: bool = False):
        self.calls.append((url, force))
        return {"matched": True, "host": "example.com"}


@pytest.mark.asyncio
async def test_static_extract_calls_egress_route_gate(tmp_path):
    config = RuntimeConfig(
        artifact_dir=tmp_path / "artifacts",
        egress_routes_config_path=tmp_path / "egress-routes.json",
        egress_routes_state_path=tmp_path / "egress-routes-state.json",
    )
    manager = _StubEgressManager()
    transport = StubTransport(manager=manager)
    client = StaticWebClient(config, transport=transport, egress_routes=manager)

    await client.extract("https://example.com", max_tokens=100)

    assert manager.calls == [("https://example.com", False)]
