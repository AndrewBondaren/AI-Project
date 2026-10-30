"""Each marked line must be rejected without unrelated diagnostics."""

from app.dataModel.artifacts.references import ArtifactFormatKey
from app.dataModel.patch.registry.sectionMetadata import SectionKey
from app.dataModel.worldSnapshot.identity.publication import PlayerHeadExpectation, WorldPublicationRef
from app.dataModel.worldSnapshot.identity.refs import PlayerSnapshotRef, WorldSnapshotRef
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
from app.dataModel.worldSnapshot.sections.refs import SectionHistoryRef, SectionStateRef
from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.patch.changes.header import PatchHeader
from app.dataModel.patch.sections.section import DomainSection, SectionHeader
from app.dataModel.patch.request.patchSet import PatchSet
from app.dataModel.patch.preconditions.runtime import TargetVersionExpected, TargetPresence
from app.dataModel.patch.results.sectionResult import SectionRefused
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError


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


def needs_patch_request(request: PatchSet[DomainSection[PatchHeader]]) -> None:
    pass


def different_payloads(header: SectionHeader, artifact: ArtifactRef,
                       wrong_request: PatchSet[DomainSection[ArtifactRef]],
                       diagnostic: FieldPathError) -> None:
    DomainSection[PatchHeader](header=header, patches=(artifact,))  # EXPECT: reportArgumentType
    needs_patch_request(wrong_request)  # EXPECT: reportArgumentType
    TargetVersionExpected(version=artifact, presence=TargetPresence.PRESENT)  # EXPECT: reportArgumentType
    SectionRefused(category="conflict", diagnostics=(diagnostic,))  # EXPECT: reportArgumentType

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


def needs_runtime_kind(kind: OperationKind) -> None:
    pass


def needs_phase(phase: OperationPhase) -> None:
    pass


def needs_holder(holder: ArtifactHolderRef) -> None:
    pass


def different_lifecycle_types(world: WorldSnapshotRef, player: PlayerSnapshotRef,
                              lease: OperationLeaseRef, state: SectionStateRef,
                              commit: SnapshotCommitRefs, publication: WorldPublicationRef) -> None:
    SnapshotCommitRefs(world_snapshot=player, player_snapshots=(), publication=publication)  # EXPECT: reportArgumentType
    SnapshotCommitRefs(world_snapshot=world, player_snapshots=(world,), publication=publication)  # EXPECT: reportArgumentType
    needs_runtime_kind(OperationPhase.READY)  # EXPECT: reportArgumentType
    needs_phase(SnapshotApplyOutcomeKind.COMMITTED)  # EXPECT: reportArgumentType
    needs_runtime_kind(OperationClaimKind.OWNER)  # EXPECT: reportArgumentType
    needs_outcome(PackActivationDisposition.ACTIVE)  # EXPECT: reportArgumentType
    needs_holder(lease)  # EXPECT: reportArgumentType
    OperationHolder(lease=world)  # EXPECT: reportArgumentType
    SnapshotHolder(snapshot=publication)  # EXPECT: reportArgumentType
    SnapshotApplyResult(category="committed", operation_id="op", request_fingerprint="a" * 64, committed=commit, diagnostics=())  # EXPECT: reportArgumentType
    SnapshotLogRecord(activity=SnapshotLogActivity.APPLY_STARTED, operation_id="op", world_uid="world", request_fingerprint=None, timeline_id=None, snapshot_id=None, section_key=None, outcome=OperationPhase.TERMINAL)  # EXPECT: reportArgumentType
    WorldSnapshotMetadata(ref=player, parent=None, operation_id="op", turn_id=1, created_at="2026-10-30T00:00:00.000000Z", envelope_format_version=1, base_pack_hash="a" * 64, state_refs=(), history_refs=(), retained_artifacts=())  # EXPECT: reportArgumentType
    PlayerSnapshotMetadata(ref=player, parent=world, operation_id="op", turn_id=1, created_at="2026-10-30T00:00:00.000000Z", envelope_format_version=1, state_refs=(), history_refs=(), retained_artifacts=())  # EXPECT: reportArgumentType
    WorldSnapshotMetadata(ref=world, parent=None, operation_id="op", turn_id=1, created_at="2026-10-30T00:00:00.000000Z", envelope_format_version=1, base_pack_hash="a" * 64, state_refs=(), history_refs=(state,), retained_artifacts=())  # EXPECT: reportArgumentType

from app.application.patch.contracts.sectionHandler import DomainSectionHandler, SectionContract
from app.application.patch.registry.sectionRegistry import SectionRegistry
from app.application.artifacts.contracts.formatBackend import ArtifactBackend, ArtifactFormatContract
from app.application.artifacts.registry.artifactRegistry import ArtifactFormatRegistryBinding
from app.application.worldSnapshot.contracts.commitScope import CommitScope, CommitReadScope, IDomainCommitBinding
from app.application.worldSnapshot.contracts.context import SnapshotValidationContext, SnapshotApplyContext
from app.application.worldSnapshot.storage.commitStore import IPublicationCommitStore
from app.application.worldSnapshot.storage.historyStore import ISnapshotHistoryStore
from tests.snapshotCore.support.fakeSection import FakeSection, FakeSectionHandler, FakePrepared


def write_capability(scope: CommitScope) -> None:
    pass


def wrong_handler_binding(contract: SectionContract[FakeSection],
                          handler: DomainSectionHandler[DomainSection[PatchHeader]]) -> None:
    SectionRegistry().register(contract, handler)  # EXPECT: reportArgumentType


def wrong_artifact_binding(contract: ArtifactFormatContract[bytes],
                           rows: ArtifactBackend[FakePrepared], content: FakePrepared) -> None:
    registry = ArtifactFormatRegistryBinding()
    registry.register(contract, rows)  # EXPECT: reportArgumentType
    registry.encode(contract, content)  # EXPECT: reportArgumentType


def wrong_scope_capabilities(read: CommitReadScope, binding: IDomainCommitBinding[FakeSectionHandler]) -> None:
    write_capability(read)  # EXPECT: reportArgumentType
    binding.bind(read)  # EXPECT: reportArgumentType


def wrong_context_capabilities(validation: SnapshotValidationContext, player: PlayerSnapshotRef,
                               world: WorldSnapshotRef, scope: CommitScope, read: CommitReadScope) -> None:
    SnapshotApplyContext(validation=validation, world_snapshot=player, player_snapshots=(), scope=scope)  # EXPECT: reportArgumentType
    SnapshotApplyContext(validation=validation, world_snapshot=world, player_snapshots=(), scope=read)  # EXPECT: reportArgumentType


async def wrong_history_scope(history: ISnapshotHistoryStore, read: CommitReadScope,
                              metadata: WorldSnapshotMetadata) -> None:
    await history.append(read, metadata, ())  # EXPECT: reportArgumentType


from app.application.patch.encoding.patchSetCodec import PatchSetCodec
from app.application.worldSnapshot.encoding.snapshotCodec import SnapshotEnvelopeCodec


def wrong_codec_input(codec: PatchSetCodec[FakeSection], wrong_request: PatchSet[DomainSection[PatchHeader]],
                      publication: WorldPublicationRef) -> None:
    codec.encode(wrong_request)  # EXPECT: reportArgumentType
    SnapshotEnvelopeCodec().encode(publication)  # EXPECT: reportArgumentType


from app.application.worldSnapshot.logging.snapshotLog import SnapshotLifecycleLog
from app.application.artifacts.logging.artifactLog import ArtifactLifecycleLog
from app.dataModel.artifacts.events import ArtifactLogRecord


def wrong_event_models(snapshot: SnapshotLogRecord, artifact: ArtifactLogRecord) -> None:
    SnapshotLifecycleLog().emit(artifact)  # EXPECT: reportArgumentType
    ArtifactLifecycleLog().emit(snapshot)  # EXPECT: reportArgumentType
    SnapshotLifecycleLog().emit({"activity": "apply_started"})  # EXPECT: reportArgumentType


from app.db.models.snapshotCore.historyRows import WorldSnapshotRow


def cannot_mutate_historical_sql_row(row: WorldSnapshotRow) -> None:
    row.turn_id = 2  # EXPECT: reportAttributeAccessIssue
