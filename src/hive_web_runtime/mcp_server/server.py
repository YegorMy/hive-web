from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from hive_web_runtime.action_web.browser import ActionWebRuntime
from hive_web_runtime.core.config import RuntimeConfig
from hive_web_runtime.static_web.client import StaticWebClient

config = RuntimeConfig()
static_web = StaticWebClient(config)
action_web = ActionWebRuntime(config, static_web)
mcp = FastMCP("hive-web-runtime")


@mcp.tool()
async def static_web_search(query: str, limit: int = 5, max_tokens: int = 2000) -> dict[str, Any]:
    """Cheap stateless web search through local SearXNG. Returns compact normalized results and an artifact_id."""
    return (await static_web.search(query=query, limit=limit, max_tokens=max_tokens)).model_dump()


@mcp.tool()
async def static_web_extract(url: str, max_tokens: int = 3000, format: str = "markdown") -> dict[str, Any]:
    """Cheap stateless page render/extract through local Firecrawl. Returns markdown plus artifact_id."""
    return (await static_web.extract(url=url, max_tokens=max_tokens, format=format)).model_dump()


@mcp.tool()
def static_web_get_artifact(artifact_id: str, name: str = "content.md") -> str:
    """Read a local artifact previously created by static-web/action-web."""
    return static_web.artifacts.get_text(artifact_id, name)


@mcp.tool()
async def action_web_session_create(name: str | None = None, headless: bool | None = None) -> dict[str, Any]:
    """Create a live Playwright browser session for interactive sites/forms."""
    return (await action_web.session_create(name=name, headless=headless)).model_dump()


@mcp.tool()
async def action_web_navigate(session_id: str, url: str | None = None, search_query: str | None = None) -> dict[str, Any]:
    """Navigate a live session to a URL, or use static-web search_query to find the URL first."""
    return await action_web.navigate(session_id=session_id, url=url, search_query=search_query)


@mcp.tool()
async def action_web_snapshot(session_id: str, max_tokens: int = 1200) -> dict[str, Any]:
    """Return a compact interactive snapshot: visible text and refs, not full HTML."""
    return (await action_web.snapshot(session_id=session_id, max_tokens=max_tokens)).model_dump()


@mcp.tool()
async def action_web_click(session_id: str, ref: str | None = None, selector: str | None = None, confirm_sensitive: bool = False) -> dict[str, Any]:
    """Click by snapshot ref or selector. Sensitive payment/password/2FA-looking targets require confirm_sensitive=true."""
    return await action_web.click(session_id=session_id, ref=ref, selector=selector, confirm_sensitive=confirm_sensitive)


@mcp.tool()
async def action_web_type(session_id: str, text: str, ref: str | None = None, selector: str | None = None, clear: bool = True) -> dict[str, Any]:
    """Type/fill text into a snapshot ref or selector. Do not send passwords/secrets through this tool."""
    return await action_web.type(session_id=session_id, text=text, ref=ref, selector=selector, clear=clear)


@mcp.tool()
async def action_web_press(session_id: str, key: str) -> dict[str, Any]:
    """Press a keyboard key in the live browser session, e.g. Enter, Escape, ArrowDown."""
    return await action_web.press(session_id=session_id, key=key)


@mcp.tool()
async def action_web_close(session_id: str) -> dict[str, Any]:
    """Close a live Playwright browser session."""
    return await action_web.close(session_id=session_id)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
