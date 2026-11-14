"""Runtime tick application inside the publication owner's write transaction."""
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pydantic import TypeAdapter

from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper
from app.application.worldSnapshot.validation.missingPersistedSnapshotBase import MissingPersistedSnapshotBase
from app.dataModel.worldSnapshot.metadata.metadataIssues import (
    SnapshotBuilderIssue, SnapshotMetadataCode, SnapshotMetadataFieldIssue, SnapshotMetadataRelationIssue,
)
from app.application.artifacts.contracts.holderPort import IArtifactHolders
from app.application.patch.registry.sectionRegistry import SectionRegistry
from app.application.worldSnapshot.contracts.commitScope import CommitScope
from app.application.worldSnapshot.contracts.context import SnapshotApplyContext, SnapshotValidationContext
from app.application.publication.errors import PublicationInfrastructureError
from app.application.publication.errors import OperationBindingMismatchError, OperationBusyError
from app.application.publication.contracts.operationStore import IOperationStore
from app.application.worldSnapshot.errors import SnapshotOperationCancelledError
from app.dataModel.artifacts.lifecycle.operation.claim import OperationClaim, PublicationOwner, PublicationBusy
from app.dataModel.artifacts.lifecycle.operation.kinds import OperationKind
from app.dataModel.artifacts.lifecycle.operation.record import OperationCancelled
from app.dataModel.identity.uid import EntityUid
from app.dataModel.validation.diagnostics.runtimeIssueContext import RevisionHex
from app.dataModel.worldSnapshot.results.apply import SnapshotApplyResult
from app.dataModel.worldSnapshot.results.applyIssues import SnapshotApplyCode, SnapshotApplyRelationIssue
from app.application.worldSnapshot.service.snapshotMetadataBuilder import SnapshotMetadataBuilder, SnapshotMetadataFailure
from app.application.worldSnapshot.storage.historyStore import ISnapshotHistoryStore
from app.dataModel.worldSnapshot.metadata.envelope import CreatedAtUtc, SnapshotEnvelope
from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.artifacts.lifecycle.lease import OperationLeaseRef
from app.application.worldSnapshot.storage.publicationStore import IPlayerPublicationStore, IWorldPublicationStore
from app.dataModel.patch.results.sectionResult import SectionApplyReceipt, SectionRefused
from app.dataModel.patch.sections.section import DomainSection
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.worldSnapshot.identity.refs import PlayerSnapshotRef, SnapshotRef, WorldSnapshotRef
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
from app.dataModel.worldSnapshot.results.publication import (
    CasConflictTrace, CasDecision, CasStep, CasTransactionOutcome, PlayerCasMismatch, WorldCasMismatch,
)
from app.ids.deterministicIds import runtime_uid


class _ApplyRefused(Exception):
    """Propagate a domain refusal across the outer rollback boundary."""

    def __init__(self, refusal: SectionRefused) -> None:
        super().__init__(refusal.diagnostics)
        self.refusal = refusal


class SnapshotCasConflict(Exception):
    """Escapes the enclosing publication transaction to its caller after rollback."""

    category = SnapshotApplyOutcomeKind.CONFLICT

    def __init__(self, trace: CasConflictTrace) -> None:
        super().__init__("snapshot publication conflict")
        self.trace = trace


class WorldSnapshotService:
    def __init__(self, registry: SectionRegistry, world: IWorldPublicationStore, players: IPlayerPublicationStore,
                 history: ISnapshotHistoryStore) -> None:
        self._registry = registry
        self._world = world
        self._players = players
        self._history = history

    async def _claim_publication(self, operations: IOperationStore, operation_id: EntityUid,
                                 world_uid: EntityUid, preparation_fingerprint: RevisionHex,
                                 request_fingerprint: RevisionHex) -> PublicationOwner | SnapshotApplyResult:
        """Resolve admission before target reads; the store owns its short transaction."""
        operation_id = TypeAdapter(EntityUid).validate_python(operation_id, strict=True)
        world_uid = TypeAdapter(EntityUid).validate_python(world_uid, strict=True)
        preparation_fingerprint = TypeAdapter(RevisionHex).validate_python(preparation_fingerprint, strict=True)
        request_fingerprint = TypeAdapter(RevisionHex).validate_python(request_fingerprint, strict=True)
        try:
            claim = await operations.claim_publication(OperationKind.SNAPSHOT_APPLY, operation_id, world_uid,
                                                       preparation_fingerprint, request_fingerprint)
        except OperationBindingMismatchError as error:
            mismatch = error.mismatch
            if (mismatch.operation_id != operation_id or mismatch.requested_kind is not OperationKind.SNAPSHOT_APPLY
                    or mismatch.requested_world_uid != world_uid
                    or mismatch.requested_preparation_fingerprint != preparation_fingerprint
                    or mismatch.requested_request_fingerprint != request_fingerprint):
                raise PublicationInfrastructureError("mismatch carrier describes another request") from error
            return SnapshotApplyResult(category=SnapshotApplyOutcomeKind.REJECTED,
                operation_id=operation_id, request_fingerprint=request_fingerprint, committed=None,
                diagnostics=(SnapshotApplyRelationIssue(code=SnapshotApplyCode.OPERATION_BINDING_MISMATCH,
                                                        section_key=None, player_uid=None, artifact=None),))
        claim = TypeAdapter(OperationClaim).validate_python(claim, strict=True)
        binding = claim.lease if isinstance(claim, PublicationOwner) else claim.record
        if (binding.operation_id != operation_id or binding.world_uid != world_uid
                or binding.kind is not OperationKind.SNAPSHOT_APPLY
                or binding.preparation_fingerprint != preparation_fingerprint):
            raise PublicationInfrastructureError("claim returned another immutable binding")
        if isinstance(claim, PublicationOwner):
            return claim
        record = claim.record
        if record.publication_fingerprint is not None and record.publication_fingerprint != request_fingerprint:
            raise PublicationInfrastructureError("claim returned another request binding")
        if isinstance(claim, PublicationBusy):
            raise OperationBusyError(operation_id)
        if isinstance(record.terminal, OperationCancelled):
            raise SnapshotOperationCancelledError(record.terminal)
        if not isinstance(record.terminal, SnapshotApplyResult):
            raise PublicationInfrastructureError("snapshot operation has an unexpected terminal")
        return record.terminal

    async def _append_metadata_and_handoff(
        self, context: SnapshotApplyContext, turn_id: int, created_at: CreatedAtUtc,
        receipts: tuple[SectionApplyReceipt, ...],
        *, holders: IArtifactHolders, lease: OperationLeaseRef, transferred: tuple[ArtifactRef, ...],
    ) -> None:
        """Publish derived closures and transfer selected holds in the caller's writer scope."""
        await self._append_metadata(context, turn_id, created_at, receipts)
        await holders.handoff(context.scope, lease, (context.world_snapshot, *context.player_snapshots), transferred)

    async def _append_metadata(self, context: SnapshotApplyContext, turn_id: int, created_at: CreatedAtUtc,
                               receipts: tuple[SectionApplyReceipt, ...]) -> None:
        validation = context.validation
        parents = [(None, validation.expected_world.snapshot_head),
                   *((i, head.expected_head) for i, head in enumerate(validation.expected_players))]
        bases: dict[SnapshotRef, SnapshotEnvelope] = {}
        missing: list[MissingPersistedSnapshotBase] = []
        for player_index, ref in parents:
            if ref is None:
                continue
            metadata = await self._history.read(ref, scope=context.scope.read_scope)
            if metadata is None:
                missing.append(MissingPersistedSnapshotBase(snapshot=ref, player_index=player_index))
            else:
                bases[ref] = metadata
        try:
            envelopes = SnapshotMetadataBuilder.build(context, turn_id, created_at, receipts, bases)
        except SnapshotMetadataFailure as error:
            if not missing:
                raise
            errors: ValidatorAggregationHelper[MissingPersistedSnapshotBase | SnapshotBuilderIssue] = ValidatorAggregationHelper(
                (MissingPersistedSnapshotBase, SnapshotMetadataFieldIssue, SnapshotMetadataRelationIssue))
            absent = tuple(issue.snapshot for issue in missing)
            for issue in (*missing, *error.diagnostics):
                if not (isinstance(issue, SnapshotMetadataRelationIssue) and
                        issue.code is SnapshotMetadataCode.MISSING_BASE and issue.snapshot in absent):
                    errors.add(issue)
            errors.raise_if_any(PublicationInfrastructureError)
            raise
        for envelope in envelopes:
            await self._history.append(context.scope, envelope, receipts)

    @asynccontextmanager
    async def _apply_to_target(self, scope: CommitScope, validation: SnapshotValidationContext,
                               sections: tuple[DomainSection, ...], snapshot: WorldSnapshotRef,
                               players: tuple[PlayerSnapshotRef, ...]
                               ) -> AsyncIterator[tuple[SnapshotApplyContext, tuple[SectionApplyReceipt, ...]]]:
        """Apply validated sections, allow metadata and handoff, then CAS before outer commit."""
        expected = validation.expected_world
        assigned_players = {ref.player_uid: ref for ref in players}
        expected_uids = {head.player_uid for head in validation.expected_players}
        if (len(assigned_players) != len(players) or len(expected_uids) != len(validation.expected_players)
                or assigned_players.keys() != expected_uids):
            raise ValueError("assigned player snapshots must match the expected participants")
        target = WorldPublicationRef(world_uid=expected.world_uid, publication_id=runtime_uid(),
            snapshot_head=snapshot, pack_hash=expected.pack_hash, gameplay_started=expected.gameplay_started,
            active_timeline_id=expected.active_timeline_id)
        context = SnapshotApplyContext(validation=validation, world_snapshot=snapshot,
            player_snapshots=players, scope=scope, next_publication=target)
        receipts: list[SectionApplyReceipt] = []
        for section in sections:
            # SNAPSHOT-V1-BOUNDARY: deferred domains keep their v1 contracts.
            # This dispatch accepts registered native sections; it must not adapt
            # generator output or invoke a domain's public pipeline instead of DAG.
            # See .cursor/plans/snapshot-public-contracts-dag-integration.md, section 7.
            outcome = await self._registry.resolve(section).apply(section, context)
            if isinstance(outcome, SectionRefused):
                raise _ApplyRefused(outcome)
            if outcome.section_key != section.header.key:
                raise ValueError("receipt belongs to another section")
            receipts.append(outcome)
        yield context, tuple(receipts)
        operation_id = validation.operation_id
        world_result = await self._world.compare_append(scope, expected, target)
        if isinstance(world_result, WorldCasMismatch):
            step = CasStep(world_result.operation_id, target, CasDecision.MISMATCH)
            raise SnapshotCasConflict(CasConflictTrace(world_result, (step,), CasTransactionOutcome.PENDING))
        steps = [CasStep(operation_id, target, world_result)]
        for head in validation.expected_players:
            player_target = assigned_players[head.player_uid]
            result = await self._players.compare_append(scope, head, player_target, operation_id)
            if isinstance(result, PlayerCasMismatch):
                steps.append(CasStep(result.operation_id, player_target, CasDecision.MISMATCH))
                raise SnapshotCasConflict(CasConflictTrace(result, tuple(steps), CasTransactionOutcome.PENDING))
            steps.append(CasStep(operation_id, player_target, result))
