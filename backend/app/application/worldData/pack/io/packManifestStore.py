"""Read/write manifest.json on disk."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from app.dataModel.worldPack.meta.worldPackManifest import WorldPackManifest
from app.application.worldData.pack.encoding.packManifestCodec import decode_manifest, encode_legacy_manifest, require_legacy_manifest


class PackManifestStore:
    def load(self, path: Path) -> WorldPackManifest:
        return decode_manifest(path.read_bytes())

    def legacy_head(self, path: Path, world_uid: str) -> WorldPackManifest | None:
        if not self.exists(path):
            return None
        head = self.load(path)
        require_legacy_manifest(head, world_uid=world_uid)
        return head

    def save(self, path: Path, manifest: WorldPackManifest) -> None:
        payload = encode_legacy_manifest(manifest)
        self.legacy_head(path, manifest.world_uid)
        path.parent.mkdir(parents=True, exist_ok=True)
        staged = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                             prefix=path.name + ".", suffix=".tmp", delete=False) as handle:
                staged = Path(handle.name)
                handle.write(payload.decode("utf-8"))
            os.replace(staged, path)
        finally:
            if staged is not None:
                staged.unlink(missing_ok=True)

    def exists(self, path: Path) -> bool:
        return path.is_file()
