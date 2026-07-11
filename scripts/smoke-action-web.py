#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json

from hive_web_runtime.action_web.browser import ActionWebRuntime


async def main() -> None:
    runtime = ActionWebRuntime()
    session = await runtime.session_create(name="smoke", headless=True)
    nav = await runtime.navigate(session.session_id, url="https://example.com")
    snapshot = await runtime.snapshot(session.session_id, max_tokens=600)
    close = await runtime.close(session.session_id)
    await runtime.shutdown()
    print(json.dumps({
        "session": session.model_dump(),
        "nav": nav,
        "snapshot": snapshot.model_dump(),
        "close": close,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
