"""Update planning: read a snapshot, then build a plan without repository I/O."""
from collections.abc import Mapping

from app.application.templateLibrary.packs.write.bodyDiff import body_diff
from app.application.templateLibrary.packs.domainAdapters import PackDomainAdapter
from app.application.templateLibrary.packs.lifecycleContracts import ReinstantiatePreview, ReinstantiateSnapshot
from app.application.templateLibrary.packs.referenceResolver import (
    contextualize_reference_issues, dependency_issues, reference_index,
)
from app.application.templateLibrary.packs.reinstantiate.reinstantiateFingerprint import update_fingerprint
from app.application.templateLibrary.packs.reinstantiate.reinstantiateMembers import prepare_members
from app.application.templateLibrary.packs.reinstantiate.reinstantiatePolicy import hold_candidates, plan_retention
from app.application.templateLibrary.packs.reinstantiate.reinstantiateSnapshot import load_update_snapshot
from app.ids import LibraryKind


async def prepare_update(scope, source, instance, world) -> ReinstantiatePreview:
    snapshot = await load_update_snapshot(scope, source, instance, world)
    return build_update_plan(snapshot, scope.adapters)


def build_update_plan(snapshot: ReinstantiateSnapshot,
                      adapters: Mapping[LibraryKind, PackDomainAdapter]) -> ReinstantiatePreview:
    projection = prepare_members(snapshot, adapters)
    retention = plan_retention(snapshot, projection, adapters)
    _, issues = reference_index(retention.refs, retention.members)
    issues = contextualize_reference_issues(issues, snapshot.known_members, snapshot.world.world_uid)
    issues += dependency_issues(snapshot.instance.pack_uid,
                                set(retention.dependencies) - set(retention.existing_dependencies),
                                snapshot.world.world_uid)
    metadata_fields = ('pack_name', 'display_name', 'version')
    return ReinstantiatePreview(
        pack_uid=snapshot.instance.pack_uid, source_pack_uid=snapshot.source.pack_uid,
        preview_token=update_fingerprint(snapshot, projection, retention),
        prepared=projection.prepared, removed=retention.removed, held=retention.held,
        preserved=retention.preserved, uid_map=projection.uid_map,
        diagnostics=tuple(issue.message for issue in issues), conflicts=projection.conflicts,
        metadata_changes=body_diff({key: getattr(snapshot.instance, key) for key in metadata_fields},
                                   {key: getattr(snapshot.source, key) for key in metadata_fields}),
        dependencies=retention.dependencies, resolve_issues=issues,
    )
