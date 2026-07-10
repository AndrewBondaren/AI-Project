"""Extract uploaded World Pack zip into worlds/{uid}/pack/."""

from __future__ import annotations

import hashlib
import zipfile
from pathlib import Path

from app.application.worldData.pack.worldPackPaths import WorldPackPaths


class PackImportService:
    def import_zip(self, paths: WorldPackPaths, zip_path: Path) -> dict:
        if not zipfile.is_zipfile(zip_path):
            raise ValueError("not a zip file")
        paths.root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(paths.root)
        manifest = paths.manifest_path()
        if not manifest.is_file():
            raise ValueError("pack zip must contain manifest.json at pack root")
        raw = manifest.read_bytes()
        return {
            "pack_path": str(paths.root),
            "content_hash": hashlib.sha256(raw).hexdigest(),
            "manifest": str(manifest),
        }
