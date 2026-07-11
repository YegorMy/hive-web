from __future__ import annotations

import os
from pathlib import Path
from pydantic import BaseModel, Field


class RuntimeConfig(BaseModel):
    """Runtime configuration shared by static-web, action-web, and MCP."""

    searxng_url: str = Field(default_factory=lambda: os.getenv("SEARXNG_URL", "http://localhost:8888"))
    firecrawl_url: str = Field(default_factory=lambda: os.getenv("FIRECRAWL_API_URL", "http://localhost:3002"))
    artifact_dir: Path = Field(default_factory=lambda: Path(os.getenv("HIVE_WEB_ARTIFACT_DIR", str(Path.home() / ".cache/hive-web-runtime/artifacts"))))
    egress_routes_config_path: Path = Field(default_factory=lambda: Path(os.getenv("HIVE_WEB_EGRESS_ROUTES_CONFIG", str(Path.home() / ".config/hive-web-runtime/egress-routes.json"))))
    egress_routes_state_path: Path = Field(default_factory=lambda: Path(os.getenv("HIVE_WEB_EGRESS_ROUTES_STATE", str(Path.home() / ".cache/hive-web-runtime/egress-routes-state.json"))))
    default_max_tokens: int = int(os.getenv("HIVE_WEB_DEFAULT_MAX_TOKENS", "2000"))
    browser_headless: bool = os.getenv("HIVE_WEB_BROWSER_HEADLESS", "true").lower() not in {"0", "false", "no"}
    user_agent: str = os.getenv("HIVE_WEB_USER_AGENT", "hive-web-runtime/0.1")

    def model_post_init(self, __context: object) -> None:
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        self.egress_routes_config_path = self.egress_routes_config_path.expanduser()
        self.egress_routes_state_path = self.egress_routes_state_path.expanduser()
        self.egress_routes_config_path.parent.mkdir(parents=True, exist_ok=True)
        self.egress_routes_state_path.parent.mkdir(parents=True, exist_ok=True)
