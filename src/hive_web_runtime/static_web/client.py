from __future__ import annotations

import json
from typing import Any

import httpx

from hive_web_runtime.core.artifacts import ArtifactStore, new_artifact_id
from hive_web_runtime.core.config import RuntimeConfig
from hive_web_runtime.core.tokens import count_tokens, trim_to_token_budget
from hive_web_runtime.static_web.models import ExtractResponse, SearchResponse, SearchResult
from hive_web_runtime.static_web.transport import StaticWebTransport


class StaticWebClient:
    """Cheap stateless web access through SearXNG + Firecrawl."""

    def __init__(self, config: RuntimeConfig | None = None, transport: Any | None = None):
        self.config = config or RuntimeConfig()
        self.transport = transport or StaticWebTransport(self.config.searxng_url, self.config.firecrawl_url, timeout=self.config.request_timeout_seconds)
        self.artifacts = ArtifactStore(self.config.artifact_dir)

    async def search(self, query: str, limit: int = 5, max_tokens: int | None = None) -> SearchResponse:
        max_tokens = max_tokens or self.config.default_max_tokens
        try:
            raw = await self.transport.search(
                query,
                limit,
                engines=self.config.search_engines,
                categories=self.config.search_categories,
                language=self.config.search_language,
            )
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Static search backend unavailable (searxng={self.config.searxng_url}): {exc}") from exc
        warnings = self._warnings(raw)
        results = self._normalize_results(raw, limit)
        fallback_engines = self.config.search_fallback_engines
        if not results and fallback_engines and fallback_engines != self.config.search_engines:
            try:
                fallback_raw = await self.transport.search(
                    query,
                    limit,
                    engines=fallback_engines,
                    categories=self.config.search_categories,
                    language=self.config.search_language,
                )
            except httpx.HTTPError as exc:
                warnings.append(f"fallback search failed for engines={fallback_engines}: {exc}")
                fallback_raw = {"results": []}
            fallback_results = self._normalize_results(fallback_raw, limit)
            if fallback_results:
                warnings.append(f"primary search returned no results; retried with engines={fallback_engines}")
                warnings.extend(self._warnings(fallback_raw))
                raw = fallback_raw
                results = fallback_results
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
        return SearchResponse(query=query, results=results, tokens_estimate=tokens, artifact_id=artifact_id, truncated=truncated, warnings=warnings)

    @staticmethod
    def _warnings(raw: dict[str, Any]) -> list[str]:
        warnings: list[str] = []
        for item in raw.get("unresponsive_engines", []) or []:
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                warnings.append(f"{item[0]}: {item[1]}")
            else:
                warnings.append(str(item))
        return warnings

    @staticmethod
    def _normalize_results(raw: dict[str, Any], limit: int) -> list[SearchResult]:
        results = [
            SearchResult(
                title=item.get("title") or item.get("pretty_url") or item.get("url") or "",
                url=item.get("url"),
                snippet=item.get("content") or item.get("snippet") or "",
                source=item.get("engine") or "searxng",
            )
            for item in raw.get("results", [])
            if item.get("url")
        ]
        if not results:
            for infobox in raw.get("infoboxes", []) or []:
                for url_item in infobox.get("urls", []) or []:
                    url = url_item.get("url")
                    if not url:
                        continue
                    results.append(
                        SearchResult(
                            title=url_item.get("title") or infobox.get("infobox") or url,
                            url=url,
                            snippet=infobox.get("content") or "",
                            source=infobox.get("engine") or "searxng-infobox",
                        )
                    )
                    if len(results) >= limit:
                        return results
        return results[:limit]

    async def extract(self, url: str, max_tokens: int | None = None, format: str = "markdown") -> ExtractResponse:
        max_tokens = max_tokens or self.config.default_max_tokens
        try:
            raw = await self.transport.extract(url, [format])
        except httpx.HTTPError as exc:
            raise RuntimeError(f"Extract backend unavailable (firecrawl={self.config.firecrawl_url}): {exc}") from exc
        artifact_id = new_artifact_id("extract")
        self.artifacts.put_json(artifact_id, "raw.json", raw)
        if raw.get("error") or raw.get("success") is False:
            reason = raw.get("error") or raw.get("message") or raw
            raise RuntimeError(f"Extract backend returned an error for {url}: {reason} (artifact_id={artifact_id})")
        data = raw.get("data") or raw
        markdown = data.get("markdown") or data.get("text") or data.get("html") or ""
        markdown, truncated, tokens = trim_to_token_budget(markdown, max_tokens)
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
