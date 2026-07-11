import pytest

from hive_web_runtime.static_web.client import StaticWebClient
from hive_web_runtime.static_web.models import SearchResult
from hive_web_runtime.core.config import RuntimeConfig


class StubTransport:
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
        assert formats == ["markdown"]
        return {
            "success": True,
            "data": {"title": "Example", "markdown": "# Hello\nWorld", "url": url},
        }


@pytest.mark.asyncio
async def test_static_search_normalizes_results_and_token_counts():
    client = StaticWebClient(RuntimeConfig(), transport=StubTransport())

    result = await client.search("hermes agent", limit=2, max_tokens=500)

    assert result.query == "hermes agent"
    assert len(result.results) == 2
    assert isinstance(result.results[0], SearchResult)
    assert result.results[0].title == "Hermes"
    assert result.results[0].snippet == "Agent docs"
    assert result.tokens_estimate > 0
    assert result.artifact_id.startswith("search_")


@pytest.mark.asyncio
async def test_static_extract_normalizes_firecrawl_markdown():
    client = StaticWebClient(RuntimeConfig(), transport=StubTransport())

    page = await client.extract("https://example.com", max_tokens=1000)

    assert page.url == "https://example.com"
    assert page.title == "Example"
    assert page.markdown == "# Hello\nWorld"
    assert page.tokens_estimate > 0
    assert page.artifact_id.startswith("extract_")
