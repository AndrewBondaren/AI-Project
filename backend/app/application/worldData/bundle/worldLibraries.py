"""World-owned archive inputs and explicit legacy body migration (TZ §4)."""
from app.application.worldData.libraryPacks.archiveSources import pack_to_wire, packs_from_wire
from app.application.worldData.libraryPacks.legacyPack import legacy_pack_row, legacy_member_row
from app.application.worldData.libraryPacks.errors import LibraryPackValidationError
from app.dataModel.worldBundle.libraryArchive import LibraryArchiveManifest, LibraryArchiveMember, LibraryArchivePack
from app.dataModel.worldBundle.bundleSections import BundleSection
from app.ids import LibraryKind


FLAT_KINDS = (LibraryKind.RELIEF_TEMPLATES, LibraryKind.BUILDING_TEMPLATES)


def import_libraries(data):
    packs = list(packs_from_wire(data.get(BundleSection.LIBRARY_PACKS, [])))
    source_uid = data[BundleSection.WORLD]["world_uid"]
    legacy = legacy_pack_row(source_uid)
    members, bodies, consumed = [], {}, set()
    for kind in FLAT_KINDS:
        rows = data.get(kind.value, [])
        if not rows:
            continue
        consumed.add(kind.value)
        if any(any(m.library_kind == kind.value for m in p.manifest.members) for p in packs):
            raise LibraryPackValidationError("flat bodies and pack-owned bodies cannot share a domain")
        for body in rows:
            member = legacy_member_row(kind, body["system_name"], world_uid=source_uid)
            if member.template_uid in bodies:
                raise LibraryPackValidationError("duplicate legacy body identity")
            declared = body.get("template_uid")
            if declared is not None and declared != member.template_uid:
                raise LibraryPackValidationError("legacy body UID does not match explicit legacy mapping")
            members.append(LibraryArchiveMember(library_kind=kind.value, local_uid=member.local_uid,
                template_uid=member.template_uid, source_template_uid=member.source_template_uid,
                creation_kind=member.creation_kind, source_file="bundle"))
            bodies[member.template_uid] = {key: value for key, value in body.items() if key != "template_uid"}
    if members:
        packs.append(LibraryArchivePack(LibraryArchiveManifest(pack_uid=legacy.pack_uid,
            system_name=legacy.system_name, pack_name=legacy.pack_name, display_name=legacy.display_name,
            members=members), bodies))
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
