"""Each marked line must be rejected without unrelated diagnostics."""

from app.dataModel.artifacts.references import ArtifactFormatKey
from app.dataModel.patch.registry.sectionMetadata import SectionKey
from app.dataModel.worldSnapshot.identity.publication import PlayerHeadExpectation, WorldPublicationRef
from app.dataModel.worldSnapshot.identity.refs import PlayerSnapshotRef, WorldSnapshotRef
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
from app.dataModel.worldSnapshot.sections.refs import SectionHistoryRef, SectionStateRef


def needs_section(key: SectionKey) -> None:
    pass


def needs_format(key: ArtifactFormatKey) -> None:
    pass


def needs_world(ref: WorldSnapshotRef) -> None:
    pass


def needs_history(ref: SectionHistoryRef) -> None:
    pass


def needs_state(ref: SectionStateRef) -> None:
    pass


def needs_outcome(value: SnapshotApplyOutcomeKind) -> None:
    pass


def different_keys(section: SectionKey, artifact: ArtifactFormatKey) -> None:
    needs_section(artifact)  # EXPECT: reportArgumentType
    needs_format(section)  # EXPECT: reportArgumentType


def different_refs(world: WorldSnapshotRef, player: PlayerSnapshotRef,
                   state: SectionStateRef, history: SectionHistoryRef) -> None:
    needs_world(player)  # EXPECT: reportArgumentType
    needs_history(state)  # EXPECT: reportArgumentType
    needs_state(history)  # EXPECT: reportArgumentType
    PlayerHeadExpectation(player_uid="player", expected_head=world)  # EXPECT: reportArgumentType
    WorldPublicationRef(world_uid="world", publication_id="p", pack_hash=None,
                        snapshot_head=player, active_timeline_id=None, gameplay_started=False)  # EXPECT: reportArgumentType


needs_outcome("committed")  # EXPECT: reportArgumentType
