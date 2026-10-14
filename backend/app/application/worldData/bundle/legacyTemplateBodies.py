"""Flat bundle compatibility boundary; modern manifest kinds never use shape inference."""
from app.application.jsonValidation.types import FieldPathError, ImportValidationError
from app.application.worldData.libraryPacks.legacyDomainContracts import LegacyDomainRecord, LegacyDomainShape
from app.application.worldData.libraryPacks.legacyDomainSplit import split_legacy_domains
from app.application.worldData.libraryPacks.legacyPack import legacy_member_row
from app.application.worldData.libraryPacks.uidMap import STRUCTURE_MEMBER_RENAMES, mapped_template_uid
from app.application.worldData.libraryPacks.errors import LibraryPackValidationError
from app.db.models.libraryPackMember import LibraryPackMemberRow
from app.ids import LibraryKind
from app.application.worldData.libraryPacks.domainAdapters.refFields import template_body_refs

TEMPLATE_FLAT_KINDS = (LibraryKind.PLOT_TEMPLATES, LibraryKind.BUILDING_TEMPLATES)
_PLOT_DISCRIMINATORS = ("plot_type", "main_building", "secondary_buildings", "occupied_footprint")


def convert_flat_template_bodies(data, packs, source_world_uid):
    records, consumed = [], set()
    for source_kind in TEMPLATE_FLAT_KINDS:
        rows = data.get(source_kind.value, [])
        if not isinstance(rows, list):
            raise ImportValidationError([FieldPathError((source_kind.value,), "expected list", code="EXPECTED_LIST")])
        if source_kind.value in data:
            consumed.add(source_kind.value)
        for index, raw in enumerate(rows):
            path = (source_kind.value, index)
            if not isinstance(raw, dict) or not isinstance(raw.get("system_name"), str):
                raise ImportValidationError([FieldPathError(path, "raw body requires system_name", code="STRICT_REQUIRED")])
            is_plot = source_kind == LibraryKind.PLOT_TEMPLATES or any(key in raw for key in _PLOT_DISCRIMINATORS)
            if is_plot and "structure" in raw:
                raise ImportValidationError([FieldPathError(path,
                    "flat body mixes plot and standalone building shapes", code="LEGACY_DOMAIN_KIND")])
            kind = LibraryKind.PLOT_TEMPLATES if is_plot else LibraryKind.BUILDING_TEMPLATES
            if any(m.library_kind == kind.value for pack in packs for m in pack.manifest.members):
                raise LibraryPackValidationError("flat bodies and pack-owned bodies cannot share a domain")
            source_uid = raw.get("template_uid")
            member = legacy_member_row(kind, raw["system_name"], world_uid=source_world_uid)
            if source_uid is not None and source_uid != member.template_uid:
                member = legacy_member_row(kind, raw["system_name"], world_uid=source_world_uid,
                                           source_template_uid=source_uid)
            body = {key: value for key, value in raw.items() if key != "template_uid"}
            records.append(LegacyDomainRecord(member, source_kind,
                LegacyDomainShape.PLOT if is_plot else LegacyDomainShape.BUILDING_OUTLINE,
                body, path, source_uid, "bundle"))
    available = tuple(LibraryPackMemberRow(m.template_uid, pack.manifest.pack_uid,
        m.library_kind, m.local_uid, m.source_template_uid, m.creation_kind)
        for pack in packs for m in pack.manifest.members)
    # Explicit former structure IDs only; never resolve by globally scanning SQL/FS.
    old_ids = {uid: mapped_template_uid(uid) for uid in STRUCTURE_MEMBER_RENAMES}
    result = split_legacy_domains(records, available_members=available, uid_maps=(old_ids,))
    converted = result.require_valid()
    owners = {member.template_uid: member.pack_uid for member in available}
    dependencies = {owners[ref.template_uid] for entry in converted
        for ref in template_body_refs(LibraryKind(entry.member.library_kind), entry.prepared,
                                      entry.member.template_uid)
        if ref.template_uid in owners and owners[ref.template_uid] != entry.member.pack_uid}
    return converted, consumed, dependencies
