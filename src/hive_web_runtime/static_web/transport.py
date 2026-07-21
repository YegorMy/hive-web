from __future__ import annotations

import httpx


class StaticWebTransport:
    def __init__(self, searxng_url: str, firecrawl_url: str, timeout: float = 45.0):
        self.searxng_url = searxng_url.rstrip("/")
        self.firecrawl_url = firecrawl_url.rstrip("/")
        self.timeout = timeout

    async def search(
        self,
        query: str,
        limit: int,
        *,
        engines: str | None = None,
        categories: str | None = None,
        language: str = "auto",
    ) -> dict:
        params = {"q": query, "format": "json", "language": language, "safesearch": 0}
        if engines:
            params["engines"] = engines
        if categories:
            params["categories"] = categories
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(
                f"{self.searxng_url}/search",
                params=params,
            )
            response.raise_for_status()
            data = response.json()
        if limit:
            data["results"] = data.get("results", [])[:limit]
        return data

    async def extract(self, url: str, formats: list[str]) -> dict:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.firecrawl_url}/v1/scrape",
                json={"url": url, "formats": formats},
            )
            response.raise_for_status()
            return response.json()
