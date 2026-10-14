"""Pure pack identity projection; no policy, repositories or re-instantiate calls."""
from copy import deepcopy
from dataclasses import replace

from app.application.jsonValidation.types import FieldPathError, ImportValidationError
from app.application.worldData.libraryPacks.legacyPack import legacy_pack_row, legacy_source_member_row
from app.application.worldData.libraryPacks.legacyWorldContracts import LegacyPackRoute
from app.application.worldData.libraryPacks.packIdentity import instance_system_name
from app.ids import LibraryKind, library_uid, remapped_library_uid


def existing_instance(facts, source, world_uid):
    found = [p for p in facts.packs if p.pack.owner_world_uid == world_uid
             and p.pack.source_pack_uid == source.pack.pack_uid]
    if len(found) > 1:
        raise ImportValidationError([FieldPathError(("library_packs", source.pack.pack_uid),
            "multiple owned instances name this source pack", code="LEGACY_PROVENANCE")])
    return found[0] if found else None


def reuse_map(source, instance):
    managed = {}
    for entry in instance.members:
        m = entry.member
        if m.creation_kind != "pack_copy" or m.source_template_uid is None:
            continue
        if m.source_template_uid in managed:
            raise ImportValidationError([FieldPathError(("library_packs", instance.pack.pack_uid),
                "multiple pack-copy members name the same source UID", code="LEGACY_PROVENANCE")])
        managed[m.source_template_uid] = m
    result = {}
    for entry in source.members:
        row = managed.get(entry.member.template_uid)
        if row is None:
            continue
        if row.library_kind != entry.member.library_kind:
            raise ImportValidationError([FieldPathError(("library_packs", instance.pack.pack_uid, row.template_uid),
                "pack-copy provenance belongs to a different domain", code="LEGACY_PROVENANCE")])
        result[entry.member.template_uid] = row
    return result


def project_pack(source, route, world_uid, *, instance=None, split_uids=()):
    if route == LegacyPackRoute.REUSE:
        return deepcopy(instance.pack), reuse_map(source, instance)
    if route == LegacyPackRoute.LEGACY:
        pack = legacy_pack_row(world_uid)
        rows = {e.member.template_uid: (deepcopy(e.member) if e.member.pack_uid == pack.pack_uid
            and e.member.template_uid not in split_uids else
            legacy_source_member_row(LibraryKind(e.member.library_kind), e.member.local_uid,
                world_uid=world_uid, source_template_uid=e.member.template_uid)) for e in source.members}
        return pack, rows
    name = instance_system_name(world_uid, source.pack.system_name)
    uid = library_uid(LibraryKind.LIBRARY_PACKS, name)
    pack = replace(source.pack, pack_uid=uid, system_name=name, owner_world_uid=world_uid,
                   source_pack_uid=source.pack.pack_uid)
    rows = {e.member.template_uid: replace(e.member,
        template_uid=remapped_library_uid(LibraryKind(e.member.library_kind), target_pack_uid=uid,
                                         source_template_uid=e.member.template_uid),
        pack_uid=uid, source_template_uid=e.member.template_uid, creation_kind="pack_copy") for e in source.members}
    return pack, rows
