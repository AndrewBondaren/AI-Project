"""FS / pack import for relief templates (R29) — RELIEF-T-12.

Separated from SQL CRUD in ``ReliefTemplateLibraryService``.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path

from app.application.worldData.reliefErrors import ReliefNotFoundError, ReliefValidationError
from app.application.worldData.reliefTemplateLibraryService import (
    DOMAIN_ROOT,
    resolve_relief_domain_root,
)
from app.db.models.reliefTemplate import ReliefTemplateRow

logger = logging.getLogger(__name__)

UpsertFromDict = Callable[..., Awaitable[ReliefTemplateRow]]


async def import_relief_path(
    path: str | Path,
    *,
    upsert_from_dict: UpsertFromDict,
    domain_root: Path | None = None,
    enforce_domain_root: bool = True,
) -> list[ReliefTemplateRow]:
    """Import a single JSON file or a pack directory under relief_templates/."""
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
        return [await _import_file(p, pack_name=None, domain_root=root, upsert=upsert_from_dict)]
    if p.is_dir():
        return await _import_pack_dir(p, domain_root=root, upsert=upsert_from_dict)
    raise ReliefValidationError(f"Not a file or directory: {path}")


async def _import_pack_dir(
    pack_dir: Path,
    *,
    domain_root: Path,
    upsert: UpsertFromDict,
) -> list[ReliefTemplateRow]:
    pack_name = pack_dir.name
    if pack_dir.parent.resolve() != domain_root.resolve():
        msg = (
            f"pack folder must be direct child of {domain_root.name}/ "
            f"(got {pack_dir})"
        )
        logger.warning("relief | library reject %s", msg)
        raise ReliefValidationError(msg)
    rows: list[ReliefTemplateRow] = []
    for file in sorted(pack_dir.glob("*.json")):
        rows.append(
            await _import_file(file, pack_name=pack_name, domain_root=domain_root, upsert=upsert)
        )
    if not rows:
        raise ReliefValidationError(f"No JSON files in pack {pack_dir}")
    return rows


async def _import_file(
    file: Path,
    *,
    pack_name: str | None,
    domain_root: Path,
    upsert: UpsertFromDict,
) -> ReliefTemplateRow:
    stem = file.stem
    try:
        raw = json.loads(file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning("relief | library reject bad JSON %s: %s", file, exc)
        raise ReliefValidationError(f"Invalid JSON: {file}") from exc
    if not isinstance(raw, dict):
        raise ReliefValidationError(f"Template JSON must be object: {file}")
    source = _source_file_label(file, pack_name=pack_name, domain_root=domain_root)
    return await upsert(raw, source_file=source, expected_stem=stem)


def _source_file_label(
    file: Path,
    *,
    pack_name: str | None,
    domain_root: Path,
) -> str:
    try:
        rel = file.resolve().relative_to(domain_root.resolve())
        return f"{DOMAIN_ROOT}/{rel.as_posix()}"
    except ValueError:
        if pack_name:
            return f"{DOMAIN_ROOT}/{pack_name}/{file.name}"
        return f"{DOMAIN_ROOT}/{file.name}"
