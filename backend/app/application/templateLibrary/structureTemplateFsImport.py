"""FS / pack import for structure templates — pack-owned identity (model A).

Separated from SQL CRUD in ``StructureTemplateLibraryService``.

Pack import requires ``pack.manifest.json`` (TZ §4): bodies come from the
manifest's member list, the manifest file itself is never scanned as a body,
and lone ``*.json`` files directly under the domain root are rejected —
a template exists only as a declared pack member (decision 2026-10-08).

``load_structure_stdlib`` reads only the declared default packs
(``DEFAULT_LIBRARY_PACKS``), never a wildcard scan of the domain root.
"""

from __future__ import annotations

from app.application.jsonValidation.resolve import resolve_model, UnresolvedModelError

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

from app.ids import LibraryKind
from app.application.worldData.libraryPacks.defaults import default_pack_names
from app.application.worldData.libraryPacks.manifest import (
    LoadedMember,
    PackManifestError,
    load_pack_manifest,
    member_file_stem,
    require_declared_member,
    resolve_owning_pack,
    source_file_label,
)
from app.application.worldData.structureTemplateErrors import (
    StructureTemplateNotFoundError,
    StructureTemplateValidationError,
)
from app.application.worldData.structureTemplateLibraryService import (
    DOMAIN_ROOT,
    resolve_structures_domain_root,
)
from app.dataModel.locations.structure.building.structureTemplate import StructureTemplate
from app.dataModel.libraryPacks.packManifest import LibraryPackManifest
from app.db.models.structureTemplate import StructureTemplateRow

logger = logging.getLogger(__name__)

UpsertFromDict = Callable[..., Awaitable[StructureTemplateRow]]
_LIBRARY_KIND = LibraryKind.STRUCTURE_TEMPLATES


@dataclass(frozen=True)
class StructurePackImport:
    """Outcome of a filesystem import: the owning pack manifest + body rows."""

    manifest: LibraryPackManifest
    rows: list[StructureTemplateRow]


async def import_structure_templates_path(
    path: str | Path,
    *,
    upsert_from_dict: UpsertFromDict,
    domain_root: Path | None = None,
    enforce_domain_root: bool = True,
) -> StructurePackImport:
    """Import a pack directory or a single declared member file."""
    root = (domain_root or resolve_structures_domain_root()).resolve()
    p = Path(path)
    if not p.is_absolute():
        p = (root / p).resolve()
    else:
        p = p.resolve()

    if enforce_domain_root:
        try:
            p.relative_to(root)
        except ValueError as exc:
            msg = f"path outside structures domain root {root}: {p}"
            logger.warning("structure | library reject %s", msg)
            raise StructureTemplateValidationError(msg) from exc

    if not p.exists():
        raise StructureTemplateNotFoundError(f"Path not found: {path}")
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
            raise StructureTemplateValidationError(f"Not a file or directory: {path}")
    except PackManifestError as exc:
        logger.warning("structure | library reject %s", exc)
        raise StructureTemplateValidationError(str(exc)) from exc
    rows = [
        await _import_file(member, loaded.manifest, domain_root=root, upsert=upsert_from_dict)
        for member in members
    ]
    return StructurePackImport(manifest=loaded.manifest, rows=rows)


async def _import_file(
    loaded: LoadedMember,
    manifest: LibraryPackManifest,
    *,
    domain_root: Path,
    upsert: UpsertFromDict,
) -> StructureTemplateRow:
    file = loaded.file
    member = loaded.member
    try:
        raw = json.loads(file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning("structure | library reject bad JSON %s: %s", file, exc)
        raise StructureTemplateValidationError(f"Invalid JSON: {file}") from exc
    if not isinstance(raw, dict):
        raise StructureTemplateValidationError(f"Template JSON must be object: {file}")
    source = source_file_label(file, domain_root=domain_root, root_label=DOMAIN_ROOT)
    return await upsert(
        raw,
        source_file=source,
        expected_stem=member_file_stem(member),
        pack_uid=manifest.pack_uid,
        local_uid=member.local_uid,
    )


def load_structure_stdlib(root: Path | None = None) -> list[StructureTemplate]:
    """Read the declared default packs — each via its ``pack.manifest.json``.

    Only ``DEFAULT_LIBRARY_PACKS[structure_templates]`` is read; other pack
    folders under the domain root are never touched (TZ §6).
    """
    base = (root or resolve_structures_domain_root()).resolve()
    if not base.is_dir():
        return []
    out: dict[str, StructureTemplate] = {}
    paths: dict[str, Path] = {}
    for pack_name in default_pack_names(_LIBRARY_KIND):
        try:
            loaded = load_pack_manifest(
                base / pack_name, domain_root=base, library_kind=_LIBRARY_KIND
            )
        except PackManifestError as exc:
            logger.warning("structure | library reject %s", exc)
            raise StructureTemplateValidationError(str(exc)) from exc
        for loaded_member in loaded.members:
            file = loaded_member.file
            try:
                raw = json.loads(file.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                msg = f"Invalid JSON: {file}"
                logger.warning("structure | stdlib reject %s: %s", msg, exc)
                raise StructureTemplateValidationError(msg) from exc
            try:
                outline = resolve_model(StructureTemplate, raw, label="StructureTemplate")
            except UnresolvedModelError as exc:
                msg = f"Invalid structure template JSON: {file}"
                logger.warning("structure | stdlib reject %s: %s", msg, exc)
                raise StructureTemplateValidationError(msg) from exc
            key = str(outline.system_name)
            prev = paths.get(key)
            if prev is not None:
                msg = f"duplicate structure uid '{key}': {prev} and {file}"
                logger.warning("structure | stdlib reject %s", msg)
                raise StructureTemplateValidationError(msg)
            if key != loaded_member.member.template_uid:
                msg = (
                    f"body system_name '{key}' != member template_uid "
                    f"'{loaded_member.member.template_uid}': {file}"
                )
                logger.warning("structure | stdlib reject %s", msg)
                raise StructureTemplateValidationError(msg)
            out[key] = outline
            paths[key] = file
    return [out[key] for key in sorted(out)]
