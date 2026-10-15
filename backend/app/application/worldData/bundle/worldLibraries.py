"""World-owned archive inputs and explicit legacy body migration (TZ §4)."""
from app.application.worldData.bundle import SOURCE_FILE_BUNDLE
from app.application.worldData.libraryPacks.archiveSources import pack_to_wire, packs_from_wire
from app.application.worldData.libraryPacks.legacyPack import legacy_pack_row, legacy_member_row
from app.application.worldData.libraryPacks.errors import LibraryPackValidationError
from app.dataModel.worldBundle.libraryArchive import LibraryArchiveManifest, LibraryArchiveMember, LibraryArchivePack
from app.dataModel.worldBundle.bundleSections import BundleSection
from app.ids import LibraryKind
from app.application.worldData.bundle.legacyTemplateBodies import convert_flat_template_bodies
from app.application.worldData.libraryPacks.legacyWorldInput import TEMPLATE_KINDS
from app.application.jsonValidation.types import FieldPathError, ImportValidationError


FLAT_KINDS = (LibraryKind.RELIEF_TEMPLATES,)


def import_libraries(data, *, legacy_migration=False):
    packs = list(packs_from_wire(data.get(BundleSection.LIBRARY_PACKS, [])))
    if legacy_migration:
        # B2 owns flat bodies/registries; handlers skip every template kind.
        consumed = {kind.value for kind in TEMPLATE_KINDS if data.get(kind.value)}
        return tuple(packs), consumed
    source_uid = data[BundleSection.WORLD]["world_uid"]
    legacy = legacy_pack_row(source_uid)
    members, bodies, consumed = [], {}, set()
    converted, template_consumed, dependencies = convert_flat_template_bodies(data, packs, source_uid)
    consumed.update(template_consumed)
    for entry in converted:
        member = entry.member
        members.append(LibraryArchiveMember(library_kind=member.library_kind, local_uid=member.local_uid,
            template_uid=member.template_uid, source_template_uid=member.source_template_uid,
            creation_kind=member.creation_kind, source_file=entry.source_file))
        bodies[member.template_uid] = entry.body
    for kind in FLAT_KINDS:
        rows = data.get(kind.value, [])
        if not isinstance(rows, list):
            raise ImportValidationError([FieldPathError((kind.value,), "expected list", code="EXPECTED_LIST")])
        if not rows:
            continue
        consumed.add(kind.value)
        if any(any(m.library_kind == kind.value for m in p.manifest.members) for p in packs):
            raise LibraryPackValidationError("flat bodies and pack-owned bodies cannot share a domain")
        for index, body in enumerate(rows):
            if not isinstance(body, dict) or not isinstance(body.get("system_name"), str):
                raise ImportValidationError([FieldPathError((kind.value, index),
                    "raw body requires system_name", code="STRICT_REQUIRED")])
            member = legacy_member_row(kind, body["system_name"], world_uid=source_uid)
            if member.template_uid in bodies:
                raise LibraryPackValidationError("duplicate legacy body identity")
            declared = body.get("template_uid")
            if declared is not None and declared != member.template_uid:
                raise LibraryPackValidationError("legacy body UID does not match explicit legacy mapping")
            members.append(LibraryArchiveMember(library_kind=kind.value, local_uid=member.local_uid,
                template_uid=member.template_uid, source_template_uid=member.source_template_uid,
                creation_kind=member.creation_kind, source_file=SOURCE_FILE_BUNDLE))
            bodies[member.template_uid] = {key: value for key, value in body.items() if key != "template_uid"}
    if members:
        existing = next((p for p in packs if p.manifest.pack_uid == legacy.pack_uid), None)
        if existing is not None:
            if set(existing.bodies) & bodies.keys():
                raise LibraryPackValidationError("duplicate legacy body identity")
            merged = LibraryArchivePack(existing.manifest.model_copy(update={
                "members": [*existing.manifest.members, *members],
                "dependencies": sorted(set(existing.manifest.dependencies) | dependencies)}),
                {**existing.bodies, **bodies})
            packs[packs.index(existing)] = merged
        else:
            packs.append(LibraryArchivePack(LibraryArchiveManifest(pack_uid=legacy.pack_uid,
                system_name=legacy.system_name, pack_name=legacy.pack_name, display_name=legacy.display_name,
                members=members, dependencies=sorted(dependencies)), bodies))
    if data.get(BundleSection.STRUCTURE_TEMPLATES):
        raise LibraryPackValidationError("structure bodies require library_packs membership")
    return tuple(packs), consumed


async def export_libraries(archives, bundle, world_uid):
    packs = await archives.export_world(world_uid)
    if not packs:
        return bundle
    # All world-owned members travel in the UID subtree, never a second flat body.
    kinds = {m.library_kind for p in packs for m in p.manifest.members}
    for kind in kinds:
        bundle.pop(kind, None)
    bundle[BundleSection.LIBRARY_PACKS] = [pack_to_wire(p) for p in packs]
    return bundle
