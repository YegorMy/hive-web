#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import os
import tempfile
from pathlib import Path

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ROOT = Path(__file__).resolve().parents[1]


async def main() -> None:
    env = os.environ.copy()
    env.setdefault("HIVE_WEB_ARTIFACT_DIR", tempfile.mkdtemp(prefix="hive-web-runtime-artifacts-"))
    params = StdioServerParameters(
        command="uv",
        args=["run", "--project", str(ROOT), "hive-web-runtime"],
        env=env,
    )
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            result = await session.call_tool("static_web_extract", {"url": "https://example.com", "max_tokens": 500})
            print(json.dumps({"tool_count": len(names), "tools": names, "extract_preview": result.content[0].text[:300]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
