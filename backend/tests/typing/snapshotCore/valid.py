"""Positive core identity and nominal registry-key contracts (4A1)."""

from app.dataModel.artifacts.references import (
    ArtifactFormatKey, ArtifactFormatMetadata, ArtifactFormatRegistry, ArtifactKind, ArtifactRef,
)
from app.dataModel.patch.registry.sectionMetadata import (
    PatchSectionMetadata, PatchSectionRegistry, SectionKey,
)
from app.dataModel.registryKey import RegistryKey
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex
from app.dataModel.worldSnapshot.identity.publication import PlayerHeadExpectation, WorldPublicationRef
from app.dataModel.worldSnapshot.identity.refs import PlayerSnapshotRef, SnapshotRef, WorldSnapshotRef
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
from app.dataModel.worldSnapshot.sections.refs import SectionHistoryRef, SectionStateRef


def section_state(key: SectionKey, snapshot: SnapshotRef) -> SectionStateRef:
    return SectionStateRef(snapshot=snapshot, section_key=key, format_version=1)


def history(key: SectionKey, snapshot: SnapshotRef) -> SectionHistoryRef:
    return SectionHistoryRef(snapshot=snapshot, section_key=key, format_version=1)


def artifact(key: ArtifactFormatKey, digest: RevisionHex) -> ArtifactRef:
    return ArtifactRef(kind=ArtifactKind.SQL_ROWS, format_key=key, format_version=1,
                       content_hash=digest, nbytes=100, row_count=2)


def world_publication(snapshot: WorldSnapshotRef, digest: RevisionHex) -> WorldPublicationRef:
    return WorldPublicationRef(world_uid=snapshot.world_uid, publication_id="publication",
                               pack_hash=digest, snapshot_head=snapshot,
                               active_timeline_id=snapshot.timeline_id, gameplay_started=True)


def player_head(snapshot: PlayerSnapshotRef) -> PlayerHeadExpectation:
    return PlayerHeadExpectation(player_uid=snapshot.player_uid, expected_head=snapshot)


def outcome(category: SnapshotApplyOutcomeKind) -> SnapshotApplyOutcomeKind:
    return category


section_key: SectionKey = RegistryKey[PatchSectionRegistry]("regions.state")
format_key: ArtifactFormatKey = RegistryKey[ArtifactFormatRegistry]("regions.state.rows")
section_registry = PatchSectionRegistry(entries=(
    PatchSectionMetadata(key=section_key, supported_versions=frozenset({1})),
))
format_registry = ArtifactFormatRegistry(entries=(
    ArtifactFormatMetadata(key=format_key, supported_versions=frozenset({1})),
))
category = outcome(SnapshotApplyOutcomeKind.CONFLICT)
