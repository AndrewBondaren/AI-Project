"""Deterministic ZIP64 writer — tz_template_library_packs §4.2."""

from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile, ZipInfo

from app.application.worldData.bundle.archive.errors import BundleArchiveError
from app.application.worldData.bundle.archive.validation import (
    encode_json,
    validate_blob_paths,
    validate_manifest,
    validate_source,
)
from app.dataModel.worldBundle.bundleManifest import BundleManifest
from app.dataModel.worldBundle.bundleSections import BundleArchiveLayout


def write_archive(
    sections: Mapping[str, Any],
    manifest: BundleManifest,
    pack_blobs: Mapping[str, bytes] | None = None,
    *,
    path: str | Path,
) -> Path:
    """Write atomically. Blob keys are trusted layout input, never ZIP input.

    All non-JSON blobs are stored verbatim, including already compressed zst.
    The caller owns the returned file and its eventual cleanup.
    """
    manifest = validate_manifest(manifest)
    if set(sections) != set(manifest.sections):
        raise BundleArchiveError("Sections must match the manifest index exactly")
    validate_source(manifest, sections)
    blobs = dict(pack_blobs or {})
    validate_blob_paths(blobs.keys())
    if any(not isinstance(payload, bytes) for payload in blobs.values()):
        raise BundleArchiveError("Archive blobs must be bytes")

    entries = {
        BundleArchiveLayout.MANIFEST: encode_json(
            manifest.model_dump(mode="json", exclude_none=True), BundleArchiveLayout.MANIFEST,
        ),
        **{
            manifest.sections[key]: encode_json(payload, manifest.sections[key])
            for key, payload in sections.items()
        },
        **blobs,
    }
    destination = Path(path)
    # A sibling temporary file keeps replacement atomic, including on Windows.
    fd, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", dir=destination.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(fd, "w+b") as stream:
            with ZipFile(stream, mode="w", allowZip64=True) as archive:
                for name in sorted(entries):
                    info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
                    info.create_system = 3
                    info.external_attr = 0o100644 << 16
                    info.compress_type = ZIP_DEFLATED if name.endswith(".json") else ZIP_STORED
                    archive.writestr(info, entries[name])
        os.replace(temporary_path, destination)
    finally:
        temporary_path.unlink(missing_ok=True)
    return destination
