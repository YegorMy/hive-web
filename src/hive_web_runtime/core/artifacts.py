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

    def get_text(self, artifact_id: str, name: str | None = None) -> str:
        artifact_dir = self.root / artifact_id
        if not artifact_dir.exists():
            raise FileNotFoundError(f"No artifact {artifact_id!r} under {self.root}")
        if name is None:
            for candidate in ("content.md", "snapshot.json", "results.json", "raw.json", "content.txt"):
                if (artifact_dir / candidate).exists():
                    name = candidate
                    break
        if name is None:
            available = sorted(p.name for p in artifact_dir.iterdir() if p.is_file())
            raise FileNotFoundError(f"Artifact {artifact_id!r} has no readable files; available={available}")
        path = artifact_dir / name
        if not path.exists():
            available = sorted(p.name for p in artifact_dir.iterdir() if p.is_file())
            raise FileNotFoundError(f"Artifact file {name!r} not found for {artifact_id!r}; available={available}")
        return path.read_text(encoding="utf-8")
