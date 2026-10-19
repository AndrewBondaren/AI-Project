"""World-owned archive inputs; flat template bodies are rejected (TZ §4)."""
from app.application.templateLibrary.packs.archive.archiveSources import pack_to_wire, packs_from_wire
from app.application.templateLibrary.packs.errors import LibraryPackValidationError
from app.dataModel.worldBundle.bundleSections import BundleSection


# Flat template sections (pre-pack bodies) are rejected, not migrated: on
# failure the caller still marks every claimable section consumed so nothing
# re-validates bodies the library seam already rejected.
REJECTED_FLAT_SECTIONS = (BundleSection.PLOT_TEMPLATES, BundleSection.BUILDING_TEMPLATES,
                          BundleSection.STRUCTURE_TEMPLATES, BundleSection.RELIEF_TEMPLATES)
LIBRARY_CONSUMED_SECTIONS = frozenset(REJECTED_FLAT_SECTIONS)


def import_libraries(data):
    packs = tuple(packs_from_wire(data.get(BundleSection.LIBRARY_PACKS, [])))
    flat = sorted(key for key in REJECTED_FLAT_SECTIONS if key in data)
    if flat:
        raise LibraryPackValidationError(
            "flat template body sections were removed; template bodies travel "
            "in library_packs: " + ", ".join(flat))
    return packs, frozenset()


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
