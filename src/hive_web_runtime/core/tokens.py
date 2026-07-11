from __future__ import annotations

import json
from typing import Any

try:
    import tiktoken
except Exception:  # pragma: no cover - dependency fallback
    tiktoken = None


def count_tokens(value: Any, encoding: str = "o200k_base") -> int:
    if not isinstance(value, str):
        value = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    if not value:
        return 0
    if tiktoken is None:
        return max(1, len(value) // 4)
    try:
        enc = tiktoken.get_encoding(encoding)
    except Exception:
        enc = tiktoken.get_encoding("cl100k_base")
    return len(enc.encode(value))


def trim_to_token_budget(text: str, max_tokens: int) -> tuple[str, bool, int]:
    tokens = count_tokens(text)
    if tokens <= max_tokens:
        return text, False, tokens
    ratio = max_tokens / max(tokens, 1)
    keep_chars = max(0, int(len(text) * ratio * 0.92))
    trimmed = text[:keep_chars].rstrip()
    while count_tokens(trimmed) > max_tokens and len(trimmed) > 0:
        trimmed = trimmed[: int(len(trimmed) * 0.9)].rstrip()
    return trimmed + "\n\n[truncated]", True, count_tokens(trimmed)
