from __future__ import annotations

import json
from typing import Any

from hive_web_runtime.core.artifacts import ArtifactStore, new_artifact_id
from hive_web_runtime.core.config import RuntimeConfig
from hive_web_runtime.core.tokens import count_tokens, trim_to_token_budget
from hive_web_runtime.static_web.models import ExtractResponse, SearchResponse, SearchResult
from hive_web_runtime.static_web.transport import StaticWebTransport


class StaticWebClient:
    """Cheap stateless web access through SearXNG + Firecrawl."""

    def __init__(self, config: RuntimeConfig | None = None, transport: Any | None = None):
        self.config = config or RuntimeConfig()
        self.transport = transport or StaticWebTransport(self.config.searxng_url, self.config.firecrawl_url)
        self.artifacts = ArtifactStore(self.config.artifact_dir)

    async def search(self, query: str, limit: int = 5, max_tokens: int | None = None) -> SearchResponse:
        max_tokens = max_tokens or self.config.default_max_tokens
        raw = await self.transport.search(query, limit)
        results = [
            SearchResult(
                title=item.get("title") or item.get("pretty_url") or item.get("url") or "",
                url=item.get("url"),
                snippet=item.get("content") or item.get("snippet") or "",
                source=item.get("engine") or "searxng",
            )
            for item in raw.get("results", [])
            if item.get("url")
        ][:limit]
        payload = [r.model_dump() for r in results]
        text = json.dumps(payload, ensure_ascii=False)
        _, truncated, tokens = trim_to_token_budget(text, max_tokens)
        artifact_id = new_artifact_id("search")
        self.artifacts.put_json(artifact_id, "raw.json", raw)
        self.artifacts.put_json(artifact_id, "results.json", payload)
        if truncated:
            per_result = max(80, max_tokens * 3 // max(len(results), 1))
            for r in results:
                if len(r.snippet) > per_result:
                    r.snippet = r.snippet[:per_result].rstrip() + "…"
            tokens = count_tokens([r.model_dump() for r in results])
        return SearchResponse(query=query, results=results, tokens_estimate=tokens, artifact_id=artifact_id, truncated=truncated)

    async def extract(self, url: str, max_tokens: int | None = None, format: str = "markdown") -> ExtractResponse:
        max_tokens = max_tokens or self.config.default_max_tokens
        raw = await self.transport.extract(url, [format])
        data = raw.get("data") or raw
        markdown = data.get("markdown") or data.get("text") or data.get("html") or ""
        markdown, truncated, tokens = trim_to_token_budget(markdown, max_tokens)
        artifact_id = new_artifact_id("extract")
        self.artifacts.put_json(artifact_id, "raw.json", raw)
        self.artifacts.put_text(artifact_id, "content.md", data.get("markdown") or markdown)
        return ExtractResponse(
            url=data.get("url") or url,
            title=data.get("title") or data.get("metadata", {}).get("title", ""),
            markdown=markdown,
            links=data.get("links") or [],
            tokens_estimate=tokens,
            artifact_id=artifact_id,
            truncated=truncated,
        )
