from __future__ import annotations

from pydantic import BaseModel, Field


class SearchResult(BaseModel):
    title: str = ""
    url: str
    snippet: str = ""
    source: str = "searxng"


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]
    tokens_estimate: int
    artifact_id: str
    truncated: bool = False
    warnings: list[str] = Field(default_factory=list)


class ExtractResponse(BaseModel):
    url: str
    title: str = ""
    markdown: str = ""
    links: list[dict] = Field(default_factory=list)
    tokens_estimate: int
    artifact_id: str
    truncated: bool = False
