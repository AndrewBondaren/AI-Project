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
from app.dataModel.patch.changes.header import PatchHeader
from app.dataModel.patch.sections.section import DomainSection, SectionHeader
from app.dataModel.patch.request.patchSet import PatchSet
from app.dataModel.patch.preconditions.runtime import (
    RuntimeTargetVersion, TargetPresence, TargetVersionExpected,
)
from app.dataModel.patch.results.sectionResult import SectionRefused
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


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


def typed_section(header: SectionHeader, patch: PatchHeader) -> DomainSection[PatchHeader]:
    return DomainSection[PatchHeader](header=header, patches=(patch,))


def typed_request(publication: WorldPublicationRef, digest: RevisionHex,
                  section: DomainSection[PatchHeader]) -> PatchSet[DomainSection[PatchHeader]]:
    return PatchSet[DomainSection[PatchHeader]](
        format_version=1, operation_id="op", preparation_fingerprint=digest,
        world_uid=publication.world_uid, timeline_id="main", turn_id=1,
        expected_world=publication, expected_players=(), sections=(section,),
    )


def expectation(version: RuntimeTargetVersion) -> TargetVersionExpected:
    return TargetVersionExpected(version=version, presence=TargetPresence.DELETED)


def refused(diagnostic: FieldPathError) -> SectionRefused:
    return SectionRefused(category=SnapshotApplyOutcomeKind.CONFLICT, diagnostics=(diagnostic,))

from app.dataModel.worldSnapshot.metadata.envelope import WorldSnapshotMetadata, PlayerSnapshotMetadata
from app.dataModel.worldSnapshot.results.apply import SnapshotApplyResult, SnapshotCommitRefs
from app.dataModel.worldSnapshot.results.publication import PackActivationDisposition, GameplayStarted
from app.dataModel.worldSnapshot.events import SnapshotLogActivity, SnapshotLogRecord
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind, OperationPhase, OperationClaimKind
from app.dataModel.artifacts.lifecycle.operation.record import OperationRecord
from app.dataModel.artifacts.lifecycle.operation.claim import OperationClaim, PublicationOwner
from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef
from app.dataModel.artifacts.lifecycle.holders import ArtifactHolderRef, OperationHolder, SnapshotHolder
from app.dataModel.artifacts.lifecycle.gc import GcReport


def committed_result(refs: SnapshotCommitRefs, digest: RevisionHex) -> SnapshotApplyResult:
    return SnapshotApplyResult(category=SnapshotApplyOutcomeKind.COMMITTED, operation_id="op",
                               request_fingerprint=digest, committed=refs, diagnostics=())


def immutable_envelopes(world: WorldSnapshotRef, player: PlayerSnapshotRef,
                        state: SectionStateRef, history_ref: SectionHistoryRef,
                        digest: RevisionHex) -> tuple[WorldSnapshotMetadata, PlayerSnapshotMetadata]:
    return (
        WorldSnapshotMetadata(ref=world, parent=None, operation_id="op", turn_id=1,
            created_at="2026-10-30T00:00:00.000000Z", envelope_format_version=1, base_pack_hash=digest,
            state_refs=(state,), history_refs=(history_ref,), retained_artifacts=()),
        PlayerSnapshotMetadata(ref=player, parent=None, operation_id="op", turn_id=1,
            created_at="2026-10-30T00:00:00.000000Z", envelope_format_version=1,
            state_refs=(), history_refs=(), retained_artifacts=()),
    )


def typed_lifecycle(lease: OperationLeaseRef, record: OperationRecord,
                    snapshot: SnapshotRef) -> tuple[OperationClaim, ArtifactHolderRef, GcReport]:
    claim: OperationClaim = PublicationOwner(lease=lease)
    holder: ArtifactHolderRef = SnapshotHolder(snapshot=snapshot)
    return claim, holder, GcReport(deleted=(), retained=record.leased_artifacts, failed=())


def lifecycle_event(digest: RevisionHex) -> SnapshotLogRecord:
    return SnapshotLogRecord(activity=SnapshotLogActivity.APPLY_COMMITTED, operation_id="op", world_uid="world",
        request_fingerprint=digest, timeline_id=None, snapshot_id=None, section_key=None,
        outcome=SnapshotApplyOutcomeKind.COMMITTED)

from app.application.patch.contracts.sectionHandler import DomainSectionHandler, SectionContract
from app.application.patch.registry.sectionRegistry import SectionRegistry
from app.application.artifacts.contracts.formatBackend import ArtifactBackend, ArtifactFormatContract
from app.application.artifacts.registry.artifactRegistry import ArtifactFormatRegistryBinding
from app.application.worldSnapshot.contracts.commitScope import CommitScope, CommitReadScope, IDomainCommitBinding
from app.application.worldSnapshot.contracts.context import SnapshotValidationContext, SnapshotApplyContext
from app.application.worldSnapshot.storage.commitStore import IPublicationCommitStore
from app.application.worldSnapshot.storage.historyStore import ISnapshotHistoryStore
from tests.snapshotCore.support.fakeSection import FakeSection, FakeSectionHandler, FakePrepared


def register_typed_sections(contract: SectionContract[FakeSection], handler: FakeSectionHandler,
                            section: FakeSection) -> bytes:
    registry = SectionRegistry()
    registry.register(contract, handler)
    return registry.resolve(section).encode(section)


def register_typed_artifacts(contract: ArtifactFormatContract[FakePrepared],
                             backend: ArtifactBackend[FakePrepared], content: FakePrepared) -> bytes:
    registry = ArtifactFormatRegistryBinding()
    registry.register(contract, backend)
    exact_backend: ArtifactBackend[FakePrepared] = registry.resolve(contract)
    return registry.encode(exact_backend.contract, content)


async def pinned_publication_reads(store: IPublicationCommitStore, history: ISnapshotHistoryStore,
                                   ref: SnapshotRef) -> None:
    async with store.transaction("op") as scope:
        read_scope: CommitReadScope = scope.read_scope
        await history.read(ref, scope=read_scope)


def bound_domain_storage(binding: IDomainCommitBinding[FakeSectionHandler], scope: CommitScope) -> FakeSectionHandler:
    return binding.bind(scope)


from app.application.patch.encoding.patchSetCodec import PatchSetCodec
from app.application.worldSnapshot.encoding.snapshotCodec import SnapshotEnvelopeCodec


def typed_patch_codec(codec: PatchSetCodec[FakeSection], request: PatchSet[FakeSection]) -> PatchSet[FakeSection]:
    return codec.decode(codec.encode(request))


def typed_snapshot_codec(world: WorldSnapshotMetadata, player: PlayerSnapshotMetadata) -> tuple[bytes, bytes]:
    codec = SnapshotEnvelopeCodec()
    return codec.encode(world), codec.encode(player)


from app.application.worldSnapshot.logging.snapshotLog import SnapshotLifecycleLog
from app.application.artifacts.logging.artifactLog import ArtifactLifecycleLog
from app.dataModel.artifacts.events import ArtifactLogRecord


def typed_lifecycle_emitters(snapshot: SnapshotLogRecord, artifact: ArtifactLogRecord) -> None:
    SnapshotLifecycleLog().emit(snapshot)
    ArtifactLifecycleLog().emit(artifact)
