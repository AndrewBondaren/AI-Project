"""FS / pack import for structure templates — model A uid files.

Separated from SQL CRUD in ``StructureTemplateLibraryService``.
"""

from __future__ import annotations

from app.application.jsonValidation.resolve import ResolveContext, resolve_model, UnresolvedModelError

import json
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from app.application.worldData.structureTemplateErrors import (
    StructureTemplateNotFoundError,
    StructureTemplateValidationError,
)
from app.application.worldData.structureTemplateLibraryService import (
    DOMAIN_ROOT,
    resolve_structures_domain_root,
)
from app.dataModel.locations.structure.building.structureTemplate import StructureTemplate
from app.db.models.structureTemplate import StructureTemplateRow

logger = logging.getLogger(__name__)

UpsertFromDict = Callable[..., Awaitable[StructureTemplateRow]]


async def import_structure_templates_path(
    path: str | Path,
    *,
    upsert_from_dict: UpsertFromDict,
    domain_root: Path | None = None,
    enforce_domain_root: bool = True,
) -> list[StructureTemplateRow]:
    """Import a single JSON file or a pack directory under structures_templates/."""
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
    if p.is_file():
        return [await _import_file(p, domain_root=root, upsert=upsert_from_dict)]
    if p.is_dir():
        return await _import_pack_dir(p, domain_root=root, upsert=upsert_from_dict)
    raise StructureTemplateValidationError(f"Not a file or directory: {path}")


async def _import_pack_dir(
    pack_dir: Path,
    *,
    domain_root: Path,
    upsert: UpsertFromDict,
) -> list[StructureTemplateRow]:
    pack_name = pack_dir.name
    if pack_dir.parent.resolve() != domain_root.resolve():
        msg = (
            f"pack folder must be direct child of {domain_root.name}/ "
            f"(got {pack_dir})"
        )
        logger.warning("structure | library reject %s", msg)
        raise StructureTemplateValidationError(msg)
    rows: list[StructureTemplateRow] = []
    for file in sorted(pack_dir.glob("*.json")):
        rows.append(await _import_file(file, domain_root=domain_root, upsert=upsert))
    if not rows:
        raise StructureTemplateValidationError(f"No JSON files in pack {pack_dir}")
    return rows


async def _import_file(
    file: Path,
    *,
    domain_root: Path,
    upsert: UpsertFromDict,
) -> StructureTemplateRow:
    stem = file.stem
    try:
        raw = json.loads(file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning("structure | library reject bad JSON %s: %s", file, exc)
        raise StructureTemplateValidationError(f"Invalid JSON: {file}") from exc
    if not isinstance(raw, dict):
        raise StructureTemplateValidationError(f"Template JSON must be object: {file}")
    try:
        rel = file.resolve().relative_to(domain_root.resolve())
        source = f"{DOMAIN_ROOT}/{rel.as_posix()}"
    except ValueError:
        source = f"{DOMAIN_ROOT}/{file.name}"
    return await upsert(raw, source_file=source, expected_stem=stem)


def load_structure_stdlib(root: Path | None = None) -> list[StructureTemplate]:
    """Scan ``{root}/*.json`` and ``{root}/*/*.json`` → POJOs, uid-keyed."""
    base = (root or resolve_structures_domain_root()).resolve()
    if not base.is_dir():
        return []
    files = sorted(base.glob("*.json")) + sorted(base.glob("*/*.json"))
    out: dict[str, StructureTemplate] = {}
    paths: dict[str, Path] = {}
    for file in files:
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
        out[key] = outline
        paths[key] = file
    return [out[key] for key in sorted(out)]
