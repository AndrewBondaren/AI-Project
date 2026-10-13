"""UID archives to common writer inputs; no FS import or persistence (TZ §4)."""
from dataclasses import asdict

from app.application.worldData.libraryPacks.defaults import is_default_pack_uid
from app.application.worldData.libraryPacks.errors import LibraryPackValidationError
from app.application.worldData.libraryPacks.writeInspectionContracts import WriteImportMember, WriteImportSource
from app.dataModel.worldBundle.libraryArchive import LibraryArchiveManifest, LibraryArchiveMember, LibraryArchivePack
from app.db.models.libraryPack import LibraryPackRow
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.ids import LibraryKind, library_uid, remapped_library_uid


def pack_to_wire(pack: LibraryArchivePack) -> dict:
    return {"manifest": pack.manifest.model_dump(mode="json"), "bodies": dict(pack.bodies)}


def packs_from_wire(raw) -> tuple[LibraryArchivePack, ...]:
    if not isinstance(raw, list):
        raise LibraryPackValidationError("library_packs must be an array")
    result = []
    for entry in raw:
        if not isinstance(entry, dict) or set(entry) != {"manifest", "bodies"}:
            raise LibraryPackValidationError("library pack requires manifest and UID-keyed bodies")
        manifest = LibraryArchiveManifest.model_validate(entry["manifest"])
        bodies = entry["bodies"]
        if not isinstance(bodies, dict) or any(not isinstance(body, dict) for body in bodies.values()):
            raise LibraryPackValidationError("library bodies must be UID-keyed JSON objects")
        result.append(LibraryArchivePack(manifest, bodies))
    return tuple(result)


def archive_source(pack: LibraryArchivePack, *, owner: str | None, supported) -> WriteImportSource:
    manifest = pack.manifest
    if manifest.defaults:
        raise LibraryPackValidationError("manifest defaults is a deferred extension; see tz_library_contextual_fallback.md")
    if manifest.model_extra or any(m.model_extra for m in manifest.members):
        raise LibraryPackValidationError("unsupported archive manifest metadata")
    if is_default_pack_uid(manifest.pack_uid):
        raise LibraryPackValidationError("archive cannot author an engine default pack")
    if manifest.pack_uid != library_uid(LibraryKind.LIBRARY_PACKS, manifest.system_name):
        raise LibraryPackValidationError("archive pack identity mismatch")
    if len({m.template_uid for m in manifest.members}) != len(manifest.members):
        raise LibraryPackValidationError("duplicate archive member UID")
    if set(pack.bodies) != {m.template_uid for m in manifest.members}:
        raise LibraryPackValidationError("archive membership/body mismatch")
    entries = []
    for m in manifest.members:
        try:
            kind = LibraryKind(m.library_kind)
        except ValueError as exc:
            raise LibraryPackValidationError("unsupported archive library kind") from exc
        if kind not in supported:
            raise LibraryPackValidationError(f"archive domain not supported: {kind.value}")
        if m.creation_kind == "authored":
            expected = library_uid(kind, m.local_uid, pack_uid=manifest.pack_uid)
        elif m.creation_kind == "pack_copy" and m.source_template_uid:
            expected = remapped_library_uid(kind, target_pack_uid=manifest.pack_uid,
                                            source_template_uid=m.source_template_uid)
        else:
            expected = m.template_uid  # Independently minted member copies carry their UID.
        if expected != m.template_uid:
            raise LibraryPackValidationError("archive member identity mismatch")
        row = LibraryPackMemberRow(m.template_uid, manifest.pack_uid, kind.value,
                                   m.local_uid, m.source_template_uid, m.creation_kind)
        entries.append(WriteImportMember(row, pack.bodies[m.template_uid], m.source_file))
    row = LibraryPackRow(manifest.pack_uid, manifest.system_name, manifest.pack_name,
                         manifest.display_name, manifest.version, owner, manifest.source_pack_uid)
    return WriteImportSource(row, tuple(entries), tuple(manifest.dependencies))


async def export_pack(scope, uid) -> LibraryArchivePack:
    pack = await scope.packs.get_by_uid(uid)
    if pack is None:
        from app.application.worldData.libraryPacks.errors import LibraryPackNotFoundError
        raise LibraryPackNotFoundError(f"pack '{uid}' not found")
    members, bodies = [], {}
    for row in sorted(await scope.members.list_by_pack(uid), key=lambda m: m.template_uid):
        body = await scope.adapter_for(LibraryKind(row.library_kind)).read_body_row(row.template_uid)
        if body is None:
            raise LibraryPackValidationError(f"member body missing: {row.template_uid}")
        value, source_file = body
        members.append(LibraryArchiveMember(**{key: value for key, value in asdict(row).items()
                                                if key != "pack_uid"}, source_file=source_file))
        bodies[row.template_uid] = value
    if not members:
        raise LibraryPackValidationError("UID archive cannot export an empty pack")
    manifest = LibraryArchiveManifest(**{key: value for key, value in asdict(pack).items()
                                         if key != "owner_world_uid"}, members=members,
                                     dependencies=sorted(await scope.deps.required_uids(uid)))
    return LibraryArchivePack(manifest, bodies)
