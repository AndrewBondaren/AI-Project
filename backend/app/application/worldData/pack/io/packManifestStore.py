"""Read/write manifest.json on disk."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from app.dataModel.worldPack.worldPackManifest import WorldPackManifest


class PackManifestStore:
    def load(self, path: Path) -> WorldPackManifest:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return WorldPackManifest.model_validate(raw)

    def save(self, path: Path, manifest: WorldPackManifest) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = manifest.model_dump_json(indent=2)
        staged = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                             prefix=path.name + ".", suffix=".tmp", delete=False) as handle:
                staged = Path(handle.name)
                handle.write(payload)
            os.replace(staged, path)
        finally:
            if staged is not None:
                staged.unlink(missing_ok=True)

    def exists(self, path: Path) -> bool:
        return path.is_file()
