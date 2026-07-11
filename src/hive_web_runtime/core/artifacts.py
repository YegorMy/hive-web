from __future__ import annotations

import json
import time
import uuid
from pathlib import Path
from typing import Any


def new_artifact_id(prefix: str) -> str:
    return f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"


class ArtifactStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def put_json(self, artifact_id: str, name: str, payload: Any) -> str:
        d = self.root / artifact_id
        d.mkdir(parents=True, exist_ok=True)
        path = d / name
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)

    def put_text(self, artifact_id: str, name: str, text: str) -> str:
        d = self.root / artifact_id
        d.mkdir(parents=True, exist_ok=True)
        path = d / name
        path.write_text(text, encoding="utf-8")
        return str(path)

    def get_text(self, artifact_id: str, name: str = "content.txt") -> str:
        return (self.root / artifact_id / name).read_text(encoding="utf-8")
