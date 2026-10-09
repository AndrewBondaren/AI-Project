"""Filesystem pack manifest loading/validation — TZ §4, template-pack-layout.

A pack directory under a domain root is importable only via its
``pack.manifest.json``; the manifest file itself is never interpreted as a
template body. Layout invariants enforced here:

- folder name == ``pack_name``; ``pack_uid`` == ``library_uid(LIBRARY_PACKS,
  system_name)``; member ``template_uid`` == ``library_uid(kind, local_uid,
  pack_uid=pack_uid)`` — the central formula only, no local hashing;
- every member ``library_kind`` equals the domain root's kind — FS domain
  roots never mix domains;
- ``source_file`` is domain-root-relative, stays inside this pack folder,
  and its stem equals the member's file stem (``template_uid`` for
  structures — wire ``system_name == template_uid``, model A; ``local_uid``
  for name-keyed domains);
- every non-manifest ``*.json`` in the folder is a declared member;
- an FS-author manifest never declares provenance (``source_pack_uid`` /
  ``source_template_uid``) — remap output only (TZ §4).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.application.jsonValidation.resolve import UnresolvedModelError, resolve_model
from app.application.worldData.ids import LibraryKind, library_uid
from app.dataModel.libraryPacks.packManifest import (
    LibraryPackManifest,
    LibraryPackManifestMember,
)

PACK_MANIFEST_FILENAME = "pack.manifest.json"


class PackManifestError(ValueError):
    """Manifest contract violation — domain importers wrap into their error type."""


@dataclass(frozen=True)
class LoadedMember:
    member: LibraryPackManifestMember
    file: Path


@dataclass(frozen=True)
class LoadedPack:
    manifest: LibraryPackManifest
    members: list[LoadedMember]

    def member_for_file(self, file: Path) -> LoadedMember | None:
        resolved = file.resolve()
        for loaded in self.members:
            if loaded.file == resolved:
                return loaded
        return None


def member_file_stem(member: LibraryPackManifestMember) -> str:
    """Expected body-file stem: ``template_uid`` for structures (wire
    ``system_name == template_uid``, TZ §2), ``local_uid`` elsewhere."""
    if member.library_kind == LibraryKind.STRUCTURE_TEMPLATES.value:
        return member.template_uid
    return member.local_uid


def load_pack_manifest(
    pack_dir: Path,
    *,
    domain_root: Path,
    library_kind: LibraryKind,
) -> LoadedPack:
    """Read and validate ``{pack_dir}/pack.manifest.json``; resolve member files."""
    pack_dir = pack_dir.resolve()
    domain_root = domain_root.resolve()
    manifest_path = pack_dir / PACK_MANIFEST_FILENAME
    if pack_dir.parent != domain_root:
        raise PackManifestError(
            f"pack folder must be a direct child of {domain_root.name}/ (got {pack_dir})"
        )
    if not manifest_path.is_file():
        raise PackManifestError(
            f"pack '{pack_dir.name}' has no {PACK_MANIFEST_FILENAME} — "
            "templates import only as pack members (TZ §4)"
        )
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PackManifestError(f"Invalid manifest JSON: {manifest_path}") from exc
    if not isinstance(raw, dict):
        raise PackManifestError(f"Manifest must be a JSON object: {manifest_path}")
    try:
        manifest = resolve_model(
            LibraryPackManifest, raw, label=f"{PACK_MANIFEST_FILENAME} ({pack_dir.name})"
        )
    except UnresolvedModelError as exc:
        raise PackManifestError(str(exc)) from exc

    _validate_pack_fields(manifest, pack_dir)
    loaded = _resolve_members(manifest, pack_dir, domain_root, library_kind)
    _reject_undeclared_json(pack_dir, loaded)
    return LoadedPack(manifest=manifest, members=loaded)


def _validate_pack_fields(manifest: LibraryPackManifest, pack_dir: Path) -> None:
    if manifest.pack_name != pack_dir.name:
        raise PackManifestError(
            f"pack_name '{manifest.pack_name}' != folder name '{pack_dir.name}'"
        )
    try:
        expected_uid = library_uid(LibraryKind.LIBRARY_PACKS, manifest.system_name)
    except ValueError as exc:
        raise PackManifestError(str(exc)) from exc
    if manifest.pack_uid != expected_uid:
        raise PackManifestError(
            f"pack_uid '{manifest.pack_uid}' != library_uid(LIBRARY_PACKS, "
            f"'{manifest.system_name}') = '{expected_uid}'"
        )
    if manifest.source_pack_uid is not None:
        raise PackManifestError(
            "source_pack_uid is remap provenance — FS author manifests never declare it"
        )
    deps = manifest.dependencies
    if len(set(deps)) != len(deps):
        raise PackManifestError(f"duplicate dependencies in pack '{manifest.system_name}'")
    if manifest.pack_uid in deps:
        raise PackManifestError(f"pack '{manifest.system_name}' depends on itself")
    for dep in deps:
        if "|" in dep:
            raise PackManifestError(f"dependency uid must not contain '|': {dep!r}")


def _resolve_members(
    manifest: LibraryPackManifest,
    pack_dir: Path,
    domain_root: Path,
    library_kind: LibraryKind,
) -> list[LoadedMember]:
    seen_local: set[str] = set()
    seen_uid: set[str] = set()
    seen_file: set[Path] = set()
    loaded: list[LoadedMember] = []
    for member in manifest.members:
        _validate_member_identity(member, manifest, library_kind)
        if member.source_template_uid is not None:
            raise PackManifestError(
                f"member '{member.local_uid}': source_template_uid is remap "
                "provenance — FS author manifests never declare it"
            )
        file = _resolve_source_file(member, pack_dir, domain_root)
        if member.local_uid in seen_local:
            raise PackManifestError(f"duplicate local_uid '{member.local_uid}'")
        if member.template_uid in seen_uid:
            raise PackManifestError(f"duplicate template_uid '{member.template_uid}'")
        if file in seen_file:
            raise PackManifestError(f"duplicate source_file '{member.source_file}'")
        seen_local.add(member.local_uid)
        seen_uid.add(member.template_uid)
        seen_file.add(file)
        loaded.append(LoadedMember(member=member, file=file))
    if not loaded:
        raise PackManifestError(f"pack '{manifest.system_name}' declares no members")
    return loaded


def _validate_member_identity(
    member: LibraryPackManifestMember,
    manifest: LibraryPackManifest,
    library_kind: LibraryKind,
) -> None:
    try:
        kind = LibraryKind(member.library_kind)
    except ValueError as exc:
        raise PackManifestError(
            f"member '{member.local_uid}': unknown library_kind "
            f"'{member.library_kind}'"
        ) from exc
    if kind != library_kind:
        raise PackManifestError(
            f"member '{member.local_uid}': library_kind '{kind.value}' does not "
            f"belong to this domain root ({library_kind.value}) — domains never mix"
        )
    try:
        expected_uid = library_uid(kind, member.local_uid, pack_uid=manifest.pack_uid)
    except ValueError as exc:
        raise PackManifestError(f"member '{member.local_uid}': {exc}") from exc
    if member.template_uid != expected_uid:
        raise PackManifestError(
            f"member '{member.local_uid}': template_uid '{member.template_uid}' != "
            f"library_uid({kind.value}, '{member.local_uid}', pack_uid=…) "
            f"= '{expected_uid}'"
        )


def _resolve_source_file(
    member: LibraryPackManifestMember,
    pack_dir: Path,
    domain_root: Path,
) -> Path:
    rel = Path(member.source_file)
    if rel.is_absolute() or any(part == ".." for part in rel.parts):
        raise PackManifestError(
            f"member '{member.local_uid}': source_file '{member.source_file}' "
            "must be domain-root-relative and stay inside the domain root"
        )
    if len(rel.parts) != 2 or rel.parts[0] != pack_dir.name:
        raise PackManifestError(
            f"member '{member.local_uid}': source_file '{member.source_file}' "
            f"must be '{pack_dir.name}/<file>.json' inside its own pack folder"
        )
    file = (domain_root / rel).resolve()
    if file.suffix != ".json":
        raise PackManifestError(
            f"member '{member.local_uid}': source_file '{member.source_file}' "
            "is not a .json file"
        )
    if file.name == PACK_MANIFEST_FILENAME:
        raise PackManifestError(
            f"member '{member.local_uid}': {PACK_MANIFEST_FILENAME} is metadata, "
            "never a template body"
        )
    if file.stem != member_file_stem(member):
        raise PackManifestError(
            f"member '{member.local_uid}': file stem '{file.stem}' != "
            f"'{member_file_stem(member)}' (stem == local system_name)"
        )
    if not file.is_file():
        raise PackManifestError(
            f"member '{member.local_uid}': source_file '{member.source_file}' "
            "does not exist"
        )
    return file


def _reject_undeclared_json(pack_dir: Path, loaded: list[LoadedMember]) -> None:
    declared = {lm.file for lm in loaded}
    stray = [
        f.name for f in sorted(pack_dir.glob("*.json"))
        if f.resolve() not in declared and f.name != PACK_MANIFEST_FILENAME
    ]
    if stray:
        raise PackManifestError(
            f"undeclared *.json in pack '{pack_dir.name}': {stray} — "
            "every body file is a manifest member"
        )
