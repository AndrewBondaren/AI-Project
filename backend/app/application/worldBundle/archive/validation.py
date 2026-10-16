"""Shared transport checks, independent of domain handlers and storage."""

from __future__ import annotations

import json
from collections.abc import Collection, Mapping
from typing import Any

from pydantic import ValidationError

from app.application.worldData.bundle.archive.errors import BundleArchiveError
from app.dataModel.worldBundle.bundleManifest import (
    BundleKind,
    BundleManifest,
    BundleWorldSource,
)
from app.dataModel.worldBundle.bundleSections import BundleArchiveLayout, BundleSection


def validate_path(path: str, *, directory: bool = False) -> None:
    """Require one canonical relative POSIX spelling, safe on Windows too."""
    name = path[:-1] if directory and path.endswith("/") else path
    if (
        not name
        or any(char in name for char in ("\\", ":", "\x00"))
        or any(part in ("", ".", "..") for part in name.split("/"))
        or any(ord(char) < 32 for char in name)
    ):
        raise BundleArchiveError(f"Invalid archive path: {path!r}")


def validate_blob_paths(paths: Collection[str]) -> set[str]:
    """Only an explicit caller allowlist enables raw subtree files."""
    allowed = set(paths)
    if len(allowed) != len(paths):
        raise BundleArchiveError("Duplicate blob paths in archive layout")
    for path in allowed:
        validate_path(path)
        if not path.startswith((
            BundleArchiveLayout.LIBRARY_PREFIX,
            BundleArchiveLayout.PACK_PREFIX,
        )):
            raise BundleArchiveError(f"Blob path is outside supported subtrees: {path!r}")
        parts = path.split("/")
        if any("/".join(parts[:index]) in allowed for index in range(1, len(parts))):
            raise BundleArchiveError("Archive file is also used as a parent directory")
    return allowed


def validate_manifest(manifest: BundleManifest) -> BundleManifest:
    # Frozen POJOs still contain mutable dicts; revalidate before I/O.
    try:
        return BundleManifest.model_validate(manifest.model_dump(mode="python"))
    except ValidationError as exc:
        raise BundleArchiveError(f"Invalid bundle manifest: {exc}") from exc


def validate_source(manifest: BundleManifest, sections: Mapping[str, Any]) -> None:
    if manifest.kind == BundleKind.WORLD:
        world = sections.get(BundleSection.WORLD)
        if not isinstance(world, dict):
            raise BundleArchiveError("World section must be an object")
        source = manifest.source
        if not isinstance(source, BundleWorldSource) or world.get("world_uid") != source.world_uid:
            raise BundleArchiveError("source.world_uid must match the world section before remap")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ValueError(f"non-finite JSON number: {value}")


def decode_json(payload: bytes, path: str) -> Any:
    try:
        return json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_unique_object,
            parse_constant=_invalid_constant,
        )
    except (ValueError, RecursionError) as exc:
        raise BundleArchiveError(f"Invalid JSON in {path!r}: {exc}") from exc


def encode_json(payload: Any, path: str) -> bytes:
    try:
        return json.dumps(
            payload, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise BundleArchiveError(f"Cannot encode JSON for {path!r}: {exc}") from exc
