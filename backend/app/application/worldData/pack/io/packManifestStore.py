"""Read/write manifest.json on disk."""

from __future__ import annotations

import json
from pathlib import Path

from app.dataModel.worldPack.worldPackManifest import WorldPackManifest


class PackManifestStore:
    def load(self, path: Path) -> WorldPackManifest:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return WorldPackManifest.model_validate(raw)

    def save(self, path: Path, manifest: WorldPackManifest) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            manifest.model_dump_json(indent=2),
            encoding="utf-8",
        )

    def exists(self, path: Path) -> bool:
        return path.is_file()
