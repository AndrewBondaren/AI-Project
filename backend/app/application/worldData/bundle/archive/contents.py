"""Codec output; raw blobs never enter the bundle sections dictionary."""

from dataclasses import dataclass
from typing import Any

from app.dataModel.worldBundle.bundleManifest import BundleManifest


@dataclass(frozen=True)
class ArchiveContents:
    manifest: BundleManifest
    sections: dict[str, Any]
    blobs: dict[str, bytes]
