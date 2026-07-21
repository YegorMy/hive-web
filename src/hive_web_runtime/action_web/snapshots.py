from __future__ import annotations

from hive_web_runtime.core.tokens import count_tokens, trim_to_token_budget
from hive_web_runtime.action_web.models import BrowserSnapshot, InteractiveElement


def condense_snapshot(raw: dict, max_tokens: int = 1200, session_id: str | None = None, artifact_id: str | None = None) -> BrowserSnapshot:
    """Return a compact model-facing browser state, never raw HTML by default."""
    elements: list[InteractiveElement] = []
    for idx, item in enumerate(raw.get("elements", []), start=1):
        elements.append(
            InteractiveElement(
                ref=f"@{idx}",
                role=str(item.get("role") or ""),
                name=str(item.get("name") or item.get("text") or item.get("label") or "")[:300],
                value=str(item.get("value") or "")[:300],
                selector=str(item.get("selector") or ""),
            )
        )
    visible_text = str(raw.get("text") or "")
    visible_elements = elements
    summary_payload = {
        "url": raw.get("url", ""),
        "title": raw.get("title", ""),
        "visible_text": visible_text,
        "interactives": [e.model_dump(exclude={"selector"}) for e in visible_elements],
    }
    tokens = count_tokens(summary_payload)
    truncated = False
    if tokens > max_tokens:
        budget_for_text = max(80, max_tokens - count_tokens({"interactives": [e.model_dump(exclude={"selector"}) for e in elements]}))
        visible_text, truncated, _ = trim_to_token_budget(visible_text, budget_for_text)
        summary_payload["visible_text"] = visible_text
        tokens = count_tokens(summary_payload)
    while tokens > max_tokens and visible_elements:
        truncated = True
        keep = max(0, int(len(visible_elements) * 0.8))
        if keep == len(visible_elements):
            keep -= 1
        visible_elements = visible_elements[:keep]
        summary_payload["interactives"] = [e.model_dump(exclude={"selector"}) for e in visible_elements]
        tokens = count_tokens(summary_payload)
    return BrowserSnapshot(
        session_id=session_id,
        url=str(raw.get("url") or ""),
        title=str(raw.get("title") or ""),
        visible_text=visible_text,
        interactives=visible_elements,
        tokens_estimate=tokens,
        artifact_id=artifact_id,
        truncated=truncated,
    )


SNAPSHOT_JS = r"""
(() => {
  function visible(el) {
    const style = window.getComputedStyle(el);
    const rect = el.getBoundingClientRect();
    return style && style.visibility !== 'hidden' && style.display !== 'none' && rect.width > 0 && rect.height > 0;
  }
  function cssPath(el) {
    if (el.id) return '#' + CSS.escape(el.id);
    const testId = el.getAttribute('data-testid') || el.getAttribute('data-test');
    if (testId) return `[data-testid="${CSS.escape(testId)}"]`;
    const aria = el.getAttribute('aria-label');
    if (aria) return `${el.tagName.toLowerCase()}[aria-label="${CSS.escape(aria)}"]`;
    const name = el.getAttribute('name');
    if (name) return `${el.tagName.toLowerCase()}[name="${CSS.escape(name)}"]`;
    const parts = [];
    while (el && el.nodeType === Node.ELEMENT_NODE && parts.length < 6) {
      let part = el.tagName.toLowerCase();
      const parent = el.parentElement;
      if (parent) {
        const siblings = Array.from(parent.children).filter(x => x.tagName === el.tagName);
        if (siblings.length > 1) part += `:nth-of-type(${siblings.indexOf(el) + 1})`;
      }
      parts.unshift(part);
      el = parent;
    }
    return parts.join(' > ');
  }
  function roleOf(el) {
    return el.getAttribute('role') || ({A:'link', BUTTON:'button', INPUT:'textbox', TEXTAREA:'textbox', SELECT:'combobox'}[el.tagName] || el.tagName.toLowerCase());
  }
  function nameOf(el) {
    return el.getAttribute('aria-label') || el.getAttribute('placeholder') || el.innerText || el.value || el.getAttribute('name') || el.textContent || '';
  }
  const selector = 'a[href],button,input,textarea,select,[role],[contenteditable="true"],[tabindex]';
  const elements = Array.from(document.querySelectorAll(selector)).filter(visible).slice(0, 80).map(el => ({
    role: roleOf(el),
    name: nameOf(el).replace(/\s+/g, ' ').trim().slice(0, 300),
    value: ('value' in el ? String(el.value || '') : '').slice(0, 300),
    selector: cssPath(el)
  }));
  return {
    url: location.href,
    title: document.title,
    text: (document.body ? document.body.innerText : '').replace(/\s+/g, ' ').trim().slice(0, 10000),
    elements
  };
})()
"""
