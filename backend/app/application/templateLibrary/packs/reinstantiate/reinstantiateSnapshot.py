"""Read all inputs for update planning inside the caller's transaction."""
from copy import deepcopy

from app.application.templateLibrary.packs.domainAdapters.refFields import (
    named_location_template_refs,
)
from app.application.templateLibrary.packs.errors import LibraryPackValidationError
from app.application.templateLibrary.packs.lifecycleContracts import CatalogSnapshot, ReinstantiateSnapshot
from app.application.templateLibrary.packs.referenceResolver import collect_refs, load_catalog
from app.application.templateLibrary.packs.reinstantiate.reinstantiateMembers import member_identity
from app.ids import LibraryKind


async def load_update_snapshot(scope, source, instance, world) -> ReinstantiateSnapshot:
    catalog = await load_catalog(scope, world.world_uid)
    source_members = tuple(await scope.members.list_by_pack(source.pack_uid))
    source_bodies, source_files = {}, {}
    for member in source_members:
        found = await scope.adapter_for(LibraryKind(member.library_kind)).read_body_row(member.template_uid)
        if found is None:
            raise LibraryPackValidationError(f"source member '{member.template_uid}' has no body")
        source_bodies[member.template_uid], source_files[member.template_uid] = found
    current = {uid: member for uid, member in catalog.members.items() if member.pack_uid == instance.pack_uid}
    _, uid_map = member_identity(source_members, current, instance.pack_uid)
    source_catalog = CatalogSnapshot({m.template_uid: m for m in source_members}, source_bodies, source_files)
    refs = collect_refs(scope.adapters, catalog, world) + collect_refs(scope.adapters, source_catalog)
    # Ownership is diagnostic only; these rows never extend the available catalog.
    known_members = {**catalog.members, **source_catalog.members}
    lookup_uids = set(uid_map.values()) | {ref.template_uid for ref in refs}
    for uid in sorted(lookup_uids - known_members.keys()):
        member = await scope.members.get_by_uid(uid)
        if member is not None:
            known_members[uid] = member
    source_deps = tuple(sorted(await scope.deps.required_uids(source.pack_uid)))
    target_deps = tuple(sorted(await scope.deps.required_uids(instance.pack_uid)))
    existing_deps = frozenset(await scope.packs.existing_uids(sorted(set(source_deps) | set(target_deps))))
    location_refs: tuple = ()
    if scope.locations is not None:
        location_refs = named_location_template_refs(
            await scope.locations.get_by_world(world.world_uid), catalog.members)
    return deepcopy(ReinstantiateSnapshot(source, instance, world, catalog, source_members,
                                           source_bodies, source_files, known_members,
                                           source_deps, target_deps, existing_deps,
                                           location_refs=location_refs))
