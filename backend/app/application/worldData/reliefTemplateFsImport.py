"""FS / pack import for relief templates (R29) — pack-owned identity.

Separated from SQL CRUD in ``ReliefTemplateLibraryService``.

Pack import requires ``pack.manifest.json`` (TZ §4): bodies come from the
manifest's member list, the manifest file itself is never scanned as a body,
and lone ``*.json`` files directly under the domain root are rejected —
a template exists only as a declared pack member (decision 2026-10-08).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from app.application.worldData.ids import LibraryKind
from app.application.worldData.libraryPacks.manifest import (
    LoadedMember,
    LoadedPack,
    PackManifestError,
    load_pack_manifest,
    member_file_stem,
)
from app.application.worldData.reliefErrors import ReliefNotFoundError, ReliefValidationError
from app.application.worldData.reliefTemplateLibraryService import (
    DOMAIN_ROOT,
    resolve_relief_domain_root,
)
from app.dataModel.libraryPacks.packManifest import LibraryPackManifest
from app.db.models.reliefTemplate import ReliefTemplateRow

logger = logging.getLogger(__name__)

UpsertFromDict = Callable[..., Awaitable[ReliefTemplateRow]]
_LIBRARY_KIND = LibraryKind.RELIEF_TEMPLATES


@dataclass(frozen=True)
class ReliefPackImport:
    """Outcome of a filesystem import: the owning pack manifest + body rows."""

    manifest: LibraryPackManifest
    rows: list[ReliefTemplateRow]


async def import_relief_path(
    path: str | Path,
    *,
    upsert_from_dict: UpsertFromDict,
    domain_root: Path | None = None,
    enforce_domain_root: bool = True,
) -> ReliefPackImport:
    """Import a pack directory or a single declared member file."""
    root = (domain_root or resolve_relief_domain_root()).resolve()
    p = Path(path)
    if not p.is_absolute():
        p = (root / p).resolve()
    else:
        p = p.resolve()

    if enforce_domain_root:
        try:
            p.relative_to(root)
        except ValueError as exc:
            msg = f"path outside relief domain root {root}: {p}"
            logger.warning("relief | library reject %s", msg)
            raise ReliefValidationError(msg) from exc

    if not p.exists():
        raise ReliefNotFoundError(f"Path not found: {path}")
    if p.is_file():
        loaded = _load_owning_pack(p, domain_root=root)
        member = _declared_member(loaded, p)
        rows = [await _import_file(member, loaded.manifest, domain_root=root, upsert=upsert_from_dict)]
        return ReliefPackImport(manifest=loaded.manifest, rows=rows)
    if p.is_dir():
        loaded = _load_pack_dir(p, domain_root=root)
        rows = [
            await _import_file(member, loaded.manifest, domain_root=root, upsert=upsert_from_dict)
            for member in loaded.members
        ]
        return ReliefPackImport(manifest=loaded.manifest, rows=rows)
    raise ReliefValidationError(f"Not a file or directory: {path}")


def _load_pack_dir(pack_dir: Path, *, domain_root: Path) -> LoadedPack:
    try:
        return load_pack_manifest(
            pack_dir, domain_root=domain_root, library_kind=_LIBRARY_KIND
        )
    except PackManifestError as exc:
        logger.warning("relief | library reject %s", exc)
        raise ReliefValidationError(str(exc)) from exc


def _load_owning_pack(file: Path, *, domain_root: Path) -> LoadedPack:
    """The pack owning ``file`` — its parent dir under the domain root."""
    if file.parent.resolve() == domain_root.resolve():
        msg = (
            f"lone file '{file.name}' in domain root is not imported — "
            "templates arrive as members of a pack with pack.manifest.json"
        )
        logger.warning("relief | library reject %s", msg)
        raise ReliefValidationError(msg)
    return _load_pack_dir(file.parent, domain_root=domain_root)


def _declared_member(loaded: LoadedPack, file: Path) -> LoadedMember:
    member = loaded.member_for_file(file)
    if member is None:
        msg = f"file '{file.name}' is not a declared member of pack '{loaded.manifest.system_name}'"
        logger.warning("relief | library reject %s", msg)
        raise ReliefValidationError(msg)
    return member


async def _import_file(
    loaded: LoadedMember,
    manifest: LibraryPackManifest,
    *,
    domain_root: Path,
    upsert: UpsertFromDict,
) -> ReliefTemplateRow:
    file = loaded.file
    member = loaded.member
    try:
        raw = json.loads(file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning("relief | library reject bad JSON %s: %s", file, exc)
        raise ReliefValidationError(f"Invalid JSON: {file}") from exc
    if not isinstance(raw, dict):
        raise ReliefValidationError(f"Template JSON must be object: {file}")
    source = _source_file_label(file, domain_root=domain_root)
    return await upsert(
        raw,
        source_file=source,
        expected_stem=member_file_stem(member),
        pack_uid=manifest.pack_uid,
        local_uid=member.local_uid,
    )


def _source_file_label(file: Path, *, domain_root: Path) -> str:
    rel = file.resolve().relative_to(domain_root.resolve())
    return f"{DOMAIN_ROOT}/{rel.as_posix()}"
