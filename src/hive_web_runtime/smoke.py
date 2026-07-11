from __future__ import annotations

import asyncio
import json

from hive_web_runtime.core.config import RuntimeConfig
from hive_web_runtime.static_web.client import StaticWebClient


async def async_main() -> dict:
    cfg = RuntimeConfig()
    static = StaticWebClient(cfg)
    search = await static.search("Hermes Agent Nous Research web search Firecrawl", limit=3, max_tokens=1000)
    extract = await static.extract("https://example.com", max_tokens=800)
    return {
        "static_search_results": len(search.results),
        "static_search_tokens": search.tokens_estimate,
        "static_extract_title": extract.title,
        "static_extract_tokens": extract.tokens_estimate,
        "searxng_url": cfg.searxng_url,
        "firecrawl_url": cfg.firecrawl_url,
    }


def main() -> None:
    print(json.dumps(asyncio.run(async_main()), ensure_ascii=False, indent=2))
