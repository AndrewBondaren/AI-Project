"""Transaction-bound handler inputs; no query routing or domain payload assembly."""

from dataclasses import dataclass

from app.application.worldSnapshot.contracts.commitScope import CommitReadScope, CommitScope
from app.dataModel.identity.uid import EntityUid
from app.dataModel.patch.sections.dependency import SectionDependency
from app.dataModel.worldSnapshot.identity.publication import PlayerHeadExpectation, WorldPublicationRef
from app.dataModel.worldSnapshot.identity.refs import PlayerSnapshotRef, WorldSnapshotRef


@dataclass(frozen=True, slots=True)
class SnapshotValidationContext:
    operation_id: EntityUid
    expected_world: WorldPublicationRef
    expected_players: tuple[PlayerHeadExpectation, ...]
    resolved_dependencies: tuple[SectionDependency, ...]
    read_scope: CommitReadScope


@dataclass(frozen=True, slots=True)
class SnapshotApplyContext:
    validation: SnapshotValidationContext
    world_snapshot: WorldSnapshotRef
    player_snapshots: tuple[PlayerSnapshotRef, ...]
    scope: CommitScope
    next_publication: WorldPublicationRef

    def __post_init__(self) -> None:
        target = self.next_publication
        if not isinstance(target, WorldPublicationRef):
            raise TypeError("next_publication requires a WorldPublicationRef")
        WorldPublicationRef.model_validate(target, strict=True)
        expected = self.validation.expected_world
        if (target.world_uid != expected.world_uid or target.snapshot_head != self.world_snapshot
                or target.publication_id == expected.publication_id):
            raise ValueError("target must be a new publication for the assigned world snapshot")
        if (not expected.gameplay_started or target.pack_hash != expected.pack_hash
                or target.active_timeline_id != expected.active_timeline_id
                or target.active_timeline_id != self.world_snapshot.timeline_id):
            raise ValueError("runtime tick must preserve the active pack and timeline")
