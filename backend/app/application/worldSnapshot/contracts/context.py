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
