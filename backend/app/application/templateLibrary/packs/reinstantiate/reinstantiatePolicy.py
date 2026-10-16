"""Pure retention closure and dependency policy over the projected catalog."""
from app.application.worldData.libraryPacks.lifecycleContracts import (
    CatalogSnapshot, MemberProjection, ReinstantiateSnapshot, RetentionPlan,
)
from app.application.worldData.libraryPacks.referenceResolver import collect_refs, pin_index


def hold_candidates(refs, members, candidates, pins):
    """Least reachable closure; a cycle with no root cannot retain itself."""
    held = {uid: list(reasons) for uid, reasons in pins.items() if uid in candidates}
    changed = True
    while changed:
        changed = False
        for ref in refs:
            target = members.get(ref.template_uid)
            if (ref.template_uid not in candidates or target is None
                    or target.library_kind != ref.library_kind):
                continue
            if ref.consumer not in candidates or ref.consumer in held:
                if ref.template_uid not in held:
                    held[ref.template_uid] = []
                    changed = True
                if ref.reason not in held[ref.template_uid]:
                    held[ref.template_uid].append(ref.reason)
    return held


def plan_retention(snapshot: ReinstantiateSnapshot, projection: MemberProjection, adapters) -> RetentionPlan:
    projected = CatalogSnapshot(dict(snapshot.catalog.members), dict(snapshot.catalog.bodies),
                                dict(snapshot.catalog.source_files))
    for prepared in projection.prepared:
        projected.members[prepared.member.template_uid] = prepared.member
        projected.bodies[prepared.member.template_uid] = prepared.body
    # Candidate edges become roots only when their consumer is retained.
    refs = collect_refs(adapters, projected, snapshot.world) + tuple(snapshot.location_refs)
    held = hold_candidates(refs, projected.members, projection.candidates,
                           pin_index(snapshot.world, projected.members))
    removed = projection.candidates - held.keys()
    preserved = tuple(sorted(uid for uid, member in projection.current.items()
                             if member.creation_kind != 'pack_copy'))
    dependencies = tuple(sorted(set(snapshot.source_dependencies)
                                | (set(snapshot.target_dependencies) if held or preserved else set())))
    return RetentionPlan(
        {uid: member for uid, member in projected.members.items() if uid not in removed},
        tuple(ref for ref in refs if ref.consumer not in removed),
        {uid: tuple(sorted(reasons)) for uid, reasons in held.items()}, tuple(sorted(removed)),
        preserved, dependencies, tuple(uid for uid in dependencies if uid in snapshot.existing_dependencies),
    )
