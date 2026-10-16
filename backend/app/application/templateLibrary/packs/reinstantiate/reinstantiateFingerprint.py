"""Significant-input contract for preview confirmation; no I/O or policy."""
from dataclasses import asdict

from app.application.worldData.libraryPacks.lifecycleContracts import (
    MemberProjection, ReinstantiateSnapshot, RetentionPlan,
)
from app.ids import state_fingerprint


def _significant(value):
    if isinstance(value, dict):
        return {key: _significant(item) for key, item in value.items()
                if key not in ('imported_at', 'source_file')}
    if isinstance(value, list):
        return [_significant(item) for item in value]
    return value


def update_fingerprint(snapshot: ReinstantiateSnapshot, projection: MemberProjection,
                       retention: RetentionPlan) -> str:
    return state_fingerprint(_significant({
        'version': 1, 'source': asdict(snapshot.source), 'instance': asdict(snapshot.instance),
        'source_members': [asdict(m) for m in sorted(snapshot.source_members, key=lambda m: m.template_uid)],
        'source_bodies': snapshot.source_bodies,
        'members': {uid: asdict(m) for uid, m in snapshot.catalog.members.items()},
        'bodies': snapshot.catalog.bodies, 'world': asdict(snapshot.world),
        'source_deps': list(snapshot.source_dependencies), 'target_deps': list(snapshot.target_dependencies),
        'desired_deps': list(retention.dependencies), 'existing_deps': list(retention.existing_dependencies),
        'held': {uid: sorted(reasons) for uid, reasons in retention.held.items()},
        'removed': list(retention.removed), 'conflicts': sorted(projection.conflicts),
    }))
