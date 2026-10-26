"""Strict ZIP reader — transport only, no extraction or repository access."""

from __future__ import annotations

import stat
import zlib
from collections.abc import Collection
from pathlib import Path
from zipfile import BadZipFile, LargeZipFile, ZipFile, ZipInfo

from pydantic import ValidationError

from app.application.worldBundle.archive.contents import ArchiveContents
from app.application.worldBundle.archive.errors import BundleArchiveError
from app.application.worldBundle.archive.libraryLayout import (
    discover_library_layout, read_library_packs, reject_flat_duplicates,
)
from app.application.worldBundle.archive.validation import (
    decode_json,
    validate_blob_paths,
    validate_path,
    validate_source,
)
from app.dataModel.worldBundle.bundleManifest import BundleKind, BundleManifest
from app.dataModel.worldBundle.bundleSections import BundleArchiveLayout


def _inventory(archive: ZipFile) -> tuple[dict[str, ZipInfo], set[str]]:
    files: dict[str, ZipInfo] = {}
    directories: set[str] = set()
    seen: set[str] = set()
    for info in archive.infolist():
        name = info.filename
        validate_path(info.orig_filename, directory=info.is_dir())
        if info.orig_filename != name:
            raise BundleArchiveError(f"Invalid archive path: changed entry name {info.orig_filename!r}")
        validate_path(name, directory=info.is_dir())
        if name in seen:
            raise BundleArchiveError(f"Duplicate archive entry: {name!r}")
        seen.add(name)
        mode = info.external_attr >> 16
        file_type = stat.S_IFMT(mode)
        if file_type not in (0, stat.S_IFREG, stat.S_IFDIR) or stat.S_ISLNK(mode):
            raise BundleArchiveError(f"Unsupported archive entry type: {name!r}")
        if (file_type == stat.S_IFDIR and not info.is_dir()) or (
            file_type == stat.S_IFREG and info.is_dir()
        ):
            raise BundleArchiveError(f"Inconsistent directory entry: {name!r}")
        if info.flag_bits & 1:
            raise BundleArchiveError(f"Encrypted archive entry: {name!r}")
        if info.is_dir():
            if info.file_size:
                raise BundleArchiveError(f"Directory entry contains data: {name!r}")
            directories.add(name)
        else:
            files[name] = info
    return files, directories


def _read(archive: ZipFile, blob_paths: set[str]) -> ArchiveContents:
    files, directories = _inventory(archive)
    manifest_path = BundleArchiveLayout.MANIFEST
    if manifest_path not in files:
        raise BundleArchiveError("Missing bundle manifest")
    raw_manifest = decode_json(archive.read(files[manifest_path]), manifest_path)
    try:
        manifest = BundleManifest.model_validate(raw_manifest)
    except ValidationError as exc:
        raise BundleArchiveError(f"Invalid bundle manifest: {exc}") from exc
    if manifest.kind == BundleKind.LIBRARY_PACK and blob_paths:
        raise BundleArchiveError("Standalone library archive does not permit raw subtrees")

    library = discover_library_layout(
        set(files) - blob_paths, manifest, lambda path: archive.read(files[path]),
    )
    if library.paths & blob_paths:
        raise BundleArchiveError("Library layout overlaps raw blob paths")
    expected = {manifest_path, *manifest.sections.values(), *blob_paths, *library.paths}
    unknown = set(files) - expected
    missing = expected - set(files)
    if unknown:
        raise BundleArchiveError(f"Unknown archive files: {sorted(unknown)}")
    if missing:
        raise BundleArchiveError(f"Missing archive files: {sorted(missing)}")
    parents = {
        "/".join(parts[:index]) + "/"
        for name in expected
        for parts in (name.split("/"),)
        for index in range(1, len(parts))
    }
    if directories - parents:
        raise BundleArchiveError(f"Unknown archive directories: {sorted(directories - parents)}")
    if {name.rstrip("/") for name in parents} & set(files):
        raise BundleArchiveError("Archive file is also used as a parent directory")

    # Inventory and manifest are checked before any section JSON is parsed.
    sections = {
        key: decode_json(archive.read(files[path]), path)
        for key, path in manifest.sections.items()
    }
    validate_source(manifest, sections)
    reject_flat_duplicates(sections, library)
    library_packs = read_library_packs(library, lambda path: archive.read(files[path]))
    blobs = {path: archive.read(files[path]) for path in sorted(blob_paths)}
    return ArchiveContents(manifest, sections, blobs, library_packs)


def read_archive(
    path: str | Path,
    *,
    blob_paths: Collection[str] = (),
) -> ArchiveContents:
    """Read known files only; blob allowlists come from a trusted layout layer.

    C-5 library paths are derived from validated pack manifests. Opaque blobs
    still require a trusted caller allowlist; merely using a prefix grants no access.
    """
    allowed_blobs = validate_blob_paths(blob_paths)
    try:
        with ZipFile(path, mode="r", allowZip64=True) as archive:
            return _read(archive, allowed_blobs)
    except BundleArchiveError:
        raise
    except (BadZipFile, LargeZipFile, EOFError, RuntimeError, NotImplementedError, zlib.error) as exc:
        raise BundleArchiveError(f"Cannot read bundle archive: {exc}") from exc
