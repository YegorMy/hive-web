from __future__ import annotations

from pydantic import BaseModel, Field


class InteractiveElement(BaseModel):
    ref: str
    role: str = ""
    name: str = ""
    value: str = ""
    selector: str = Field(default="", exclude=True)


class BrowserSnapshot(BaseModel):
    session_id: str | None = None
    url: str
    title: str = ""
    visible_text: str = ""
    interactives: list[InteractiveElement] = Field(default_factory=list)
    tokens_estimate: int
    artifact_id: str | None = None
    truncated: bool = False


class BrowserSessionInfo(BaseModel):
    session_id: str
    headless: bool
