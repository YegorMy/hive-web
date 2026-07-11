from __future__ import annotations

TOOL_NAMES = [
    "static_web_search",
    "static_web_extract",
    "static_web_get_artifact",
    "action_web_session_create",
    "action_web_navigate",
    "action_web_snapshot",
    "action_web_click",
    "action_web_type",
    "action_web_press",
    "action_web_close",
]


def tool_names() -> list[str]:
    return list(TOOL_NAMES)
