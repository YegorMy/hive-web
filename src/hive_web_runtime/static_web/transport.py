from __future__ import annotations

import httpx

from hive_web_runtime.core.egress_routes import EgressRouteManager


class StaticWebTransport:
    def __init__(self, searxng_url: str, firecrawl_url: str, timeout: float = 45.0, egress_routes: EgressRouteManager | None = None):
        self.searxng_url = searxng_url.rstrip("/")
        self.firecrawl_url = firecrawl_url.rstrip("/")
        self.timeout = timeout
        self.egress_routes = egress_routes

    async def search(self, query: str, limit: int) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.searxng_url}/search",
                params={"q": query, "format": "json", "language": "auto", "safesearch": 0},
            )
            response.raise_for_status()
            data = response.json()
        if limit:
            data["results"] = data.get("results", [])[:limit]
        return data

    async def extract(self, url: str, formats: list[str]) -> dict:
        if self.egress_routes:
            self.egress_routes.ensure_for_url(url)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.firecrawl_url}/v1/scrape",
                json={"url": url, "formats": formats},
            )
            response.raise_for_status()
            return response.json()
