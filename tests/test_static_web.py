import pytest

from hive_web_runtime.static_web.client import StaticWebClient
from hive_web_runtime.static_web.models import SearchResult
from hive_web_runtime.core.config import RuntimeConfig


class StubTransport:
    def __init__(self):
        self.search_calls = []

    async def search(self, query: str, limit: int, **kwargs):
        self.search_calls.append((query, limit, kwargs))
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
async def test_static_search_normalizes_results_and_token_counts(tmp_path):
    config = RuntimeConfig(artifact_dir=tmp_path / "artifacts")
    transport = StubTransport()
    client = StaticWebClient(config, transport=transport)

    result = await client.search("hermes agent", limit=2, max_tokens=500)

    assert result.query == "hermes agent"
    assert len(result.results) == 2
    assert isinstance(result.results[0], SearchResult)
    assert result.results[0].title == "Hermes"
    assert result.results[0].snippet == "Agent docs"
    assert result.tokens_estimate > 0
    assert result.artifact_id.startswith("search_")
    assert transport.search_calls[0][2]["engines"] == "bing,wikipedia,wikidata"


@pytest.mark.asyncio
async def test_static_extract_normalizes_firecrawl_markdown(tmp_path):
    config = RuntimeConfig(artifact_dir=tmp_path / "artifacts")
    client = StaticWebClient(config, transport=StubTransport())

    page = await client.extract("https://example.com", max_tokens=1000)

    assert page.url == "https://example.com"
    assert page.title == "Example"
    assert page.markdown == "# Hello\nWorld"
    assert page.tokens_estimate > 0
    assert page.artifact_id.startswith("extract_")


def test_static_client_passes_configured_request_timeout(tmp_path):
    config = RuntimeConfig(artifact_dir=tmp_path / "artifacts", request_timeout_seconds=12.5)
    client = StaticWebClient(config)

    assert client.transport.timeout == 12.5


class EmptyThenFallbackTransport:
    def __init__(self):
        self.calls = []

    async def search(self, query: str, limit: int, **kwargs):
        self.calls.append(kwargs)
        if kwargs.get("engines") == "broken":
            return {"results": [], "unresponsive_engines": [["duckduckgo", "CAPTCHA"]]}
        return {"results": [{"title": "Fallback", "url": "https://example.com/fallback", "content": "works", "engine": "bing"}]}


@pytest.mark.asyncio
async def test_static_search_retries_configured_fallback_engines(tmp_path):
    config = RuntimeConfig(artifact_dir=tmp_path / "artifacts", search_engines="broken", search_fallback_engines="bing")
    transport = EmptyThenFallbackTransport()
    client = StaticWebClient(config, transport=transport)

    result = await client.search("anything", limit=2, max_tokens=500)

    assert [call["engines"] for call in transport.calls] == ["broken", "bing"]
    assert result.results[0].url == "https://example.com/fallback"
    assert "duckduckgo: CAPTCHA" in result.warnings
    assert "primary search returned no results; retried with engines=bing" in result.warnings


class InfoboxTransport:
    async def search(self, query: str, limit: int, **kwargs):
        return {
            "results": [],
            "infoboxes": [
                {
                    "infobox": "Hermes",
                    "content": "Messenger of the gods",
                    "engine": "wikipedia",
                    "urls": [{"title": "Wikipedia", "url": "https://en.wikipedia.org/wiki/Hermes"}],
                }
            ],
        }


@pytest.mark.asyncio
async def test_static_search_uses_infobox_urls_when_results_are_empty(tmp_path):
    config = RuntimeConfig(artifact_dir=tmp_path / "artifacts")
    client = StaticWebClient(config, transport=InfoboxTransport())

    result = await client.search("hermes", limit=2, max_tokens=500)

    assert result.results[0].title == "Wikipedia"
    assert result.results[0].url == "https://en.wikipedia.org/wiki/Hermes"
    assert result.results[0].source == "wikipedia"


class ErrorExtractTransport:
    async def extract(self, url: str, formats: list[str]):
        return {"success": False, "error": "boom"}


@pytest.mark.asyncio
async def test_static_extract_raises_on_backend_error_and_saves_raw(tmp_path):
    config = RuntimeConfig(artifact_dir=tmp_path / "artifacts")
    client = StaticWebClient(config, transport=ErrorExtractTransport())

    with pytest.raises(RuntimeError, match="artifact_id=extract_") as exc_info:
        await client.extract("https://example.com", max_tokens=1000)

    artifact_id = str(exc_info.value).split("artifact_id=")[1].rstrip(")")
    assert '"error": "boom"' in client.artifacts.get_text(artifact_id, "raw.json")


def test_artifact_get_text_auto_selects_available_file(tmp_path):
    config = RuntimeConfig(artifact_dir=tmp_path / "artifacts")
    config.artifact_dir.joinpath("search_1").mkdir(parents=True)
    config.artifact_dir.joinpath("search_1", "results.json").write_text("[]", encoding="utf-8")

    assert StaticWebClient(config).artifacts.get_text("search_1") == "[]"
