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

from app.ids import LibraryKind
from app.application.worldData.libraryPacks.manifest import (
    LoadedMember,
    PackManifestError,
    load_pack_manifest,
    member_file_stem,
    require_declared_member,
    resolve_owning_pack,
    source_file_label,
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
    try:
        if p.is_file():
            loaded = resolve_owning_pack(
                p, domain_root=root, library_kind=_LIBRARY_KIND
            )
            members = [require_declared_member(loaded, p)]
        elif p.is_dir():
            loaded = load_pack_manifest(
                p, domain_root=root, library_kind=_LIBRARY_KIND
            )
            members = loaded.members
        else:
            raise ReliefValidationError(f"Not a file or directory: {path}")
    except PackManifestError as exc:
        logger.warning("relief | library reject %s", exc)
        raise ReliefValidationError(str(exc)) from exc
    rows = [
        await _import_file(member, loaded.manifest, domain_root=root, upsert=upsert_from_dict)
        for member in members
    ]
    return ReliefPackImport(manifest=loaded.manifest, rows=rows)


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
    source = source_file_label(file, domain_root=domain_root, root_label=DOMAIN_ROOT)
    return await upsert(
        raw,
        source_file=source,
        expected_stem=member_file_stem(member),
        pack_uid=manifest.pack_uid,
        local_uid=member.local_uid,
    )
