import pytest

from hive_web_runtime.action_web.snapshots import condense_snapshot


@pytest.mark.asyncio
async def test_condense_snapshot_returns_compact_refs_not_full_html():
    raw = {
        "url": "https://tickets.example/search",
        "title": "Tickets",
        "text": "Search train tickets Pay now",
        "elements": [
            {"role": "textbox", "name": "From", "value": ""},
            {"role": "textbox", "name": "To", "value": ""},
            {"role": "button", "name": "Search"},
        ],
        "html": "<html>" + ("x" * 10000) + "</html>",
    }

    snap = condense_snapshot(raw, max_tokens=400)

    assert snap.url == "https://tickets.example/search"
    assert snap.interactives[0].ref == "@1"
    assert snap.interactives[1].name == "To"
    assert snap.tokens_estimate <= 400
    assert "html" not in snap.model_dump()
