"""Read-only manifest/body input for user negotiation and trusted canonical attach."""
import json
from dataclasses import dataclass
from pathlib import Path

from app.application.worldData.libraryPacks.manifest import (
    load_pack_manifest, resolve_owning_pack, require_declared_member, source_file_label,
)
from app.application.worldData.libraryPacks.packCatalog import pack_row_for, member_rows_for
from app.application.worldData.libraryPacks.writeInspectionContracts import WriteImportMember, WriteImportSource
from app.application.worldData.libraryPacks.errors import LibraryPackValidationError
from app.ids import LibraryKind


@dataclass(frozen=True)
class FsWriteSource:
    source: WriteImportSource
    single_member: bool


def read_fs_write_source(kind, path, *, domain_root=None, enforce_domain_root=True):
    kind = LibraryKind(kind)
    if kind is LibraryKind.STRUCTURE_TEMPLATES:
        from app.application.worldData.structureTemplateLibraryService import resolve_structures_domain_root, DOMAIN_ROOT
        root = domain_root or resolve_structures_domain_root()
    elif kind is LibraryKind.RELIEF_TEMPLATES:
        from app.application.worldData.reliefTemplateLibraryService import resolve_relief_domain_root, DOMAIN_ROOT
        root = domain_root or resolve_relief_domain_root()
    else:
        raise LibraryPackValidationError(f"{kind.value} has no FS pack root")
    root = Path(root).resolve()
    target = Path(path)
    target = (target if target.is_absolute() else root / target).resolve()
    if enforce_domain_root and not target.is_relative_to(root):
        raise LibraryPackValidationError(f"path outside domain root: {target}")
    if not target.exists():
        raise LibraryPackValidationError(f"Path not found: {path}")
    single = target.is_file()
    loaded = (resolve_owning_pack(target, domain_root=root, library_kind=kind) if single else
              load_pack_manifest(target, domain_root=root, library_kind=kind))
    selected = [require_declared_member(loaded, target)] if single else loaded.members
    rows = {m.template_uid: m for m in member_rows_for(loaded.manifest)}
    members = []
    for entry in selected:
        raw = json.loads(entry.file.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise LibraryPackValidationError(f"Template JSON must be object: {entry.file}")
        members.append(WriteImportMember(rows[entry.member.template_uid], raw,
            source_file_label(entry.file, domain_root=root, root_label=DOMAIN_ROOT)))
    return FsWriteSource(WriteImportSource(pack_row_for(loaded.manifest), tuple(members),
                                         tuple(loaded.manifest.dependencies)), single)
