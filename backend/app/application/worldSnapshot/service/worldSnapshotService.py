"""Runtime tick application inside the publication owner's write transaction."""
from collections.abc import AsyncIterator
from collections.abc import Mapping
from types import MappingProxyType
from contextlib import asynccontextmanager
from pydantic import BaseModel, TypeAdapter
from typing import get_args, get_origin, Union
from types import UnionType
from app.application.publication.contracts.resultBinding import PublicationResultBinding
from app.application.patch.errors import SectionHandlerContractError, PatchSetValidationClassificationError

from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper
from app.application.worldSnapshot.validation.missingPersistedSnapshotBase import MissingPersistedSnapshotBase
from app.application.artifacts.contracts.holderPort import IArtifactHolders
from app.application.patch.registry.sectionRegistry import SectionRegistry
from app.application.worldSnapshot.contracts.commitScope import CommitScope, CommitReadScope
from app.application.worldSnapshot.validation.snapshotReceiptValidator import SnapshotReceiptValidator
from app.application.worldSnapshot.validation.receiptProvenance import collect_pinned_base_issues
from app.application.worldSnapshot.service.attemptContextBuilder import SnapshotAttemptContextBuilder
from app.application.worldSnapshot.validation.preparedDependencyValidator import SnapshotPreparedDependencyValidator
from app.application.patch.encoding.sectionFingerprint import SectionFingerprint
from app.application.patch.encoding.patchSetCodec import PatchSetCodec
from app.application.worldSnapshot.validation.snapshotRequestValidator import SnapshotRequestValidator
from app.application.worldSnapshot.errors import SnapshotPublicError
from app.dataModel.worldSnapshot.errors.publicFault import SnapshotPublicFault, SnapshotPublicOperation, SnapshotPublicFailureKind
from app.dataModel.patch.request.patchSet import PatchSet
from app.dataModel.patch.sections.dependency import SectionDependency
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
from app.application.worldSnapshot.service.snapshotMetadataBuilder import SnapshotMetadataBuilder
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


class _SnapshotValidationRefused[D: BaseModel](Exception):
    """Carry checked validation diagnostics through the caller's rollback boundary."""

    def __init__(self, category: SnapshotApplyOutcomeKind,
                 diagnostics: tuple[SnapshotApplyRelationIssue | D, ...]) -> None:
        self.category = category
        self.diagnostics = diagnostics
        super().__init__(diagnostics)


class WorldSnapshotService[S: DomainSection, D: BaseModel, T: SnapshotApplyResult]:
    def __init__(self, registry: SectionRegistry[D], world: IWorldPublicationStore, players: IPlayerPublicationStore,
                 history: ISnapshotHistoryStore, *, publication_binding: PublicationResultBinding[T],
                 operations: IOperationStore[T], request_codec: PatchSetCodec[S]) -> None:
        if not isinstance(request_codec, PatchSetCodec) or request_codec.registry is not registry:
            raise ValueError("Snapshot and request codec must share the exact registry")
        if not isinstance(publication_binding, PublicationResultBinding):
            raise TypeError("expected PublicationResultBinding")
        if publication_binding is not operations.result_binding or operations.record_model is not publication_binding.record_model:
            raise ValueError("Snapshot and operation store must share the exact result binding and record model")
        annotation = publication_binding.result_model.model_fields["diagnostics"].annotation
        args = get_args(annotation)
        if get_origin(annotation) is not tuple or len(args) != 2 or args[1] is not Ellipsis:
            raise TypeError("result diagnostics require a closed tuple annotation")
        members = get_args(args[0]) if get_origin(args[0]) in (UnionType, Union) else (args[0],)
        if set(members) != {SnapshotApplyRelationIssue} | registry.diagnostic_types:
            raise ValueError("Snapshot result diagnostic roster differs from registry")
        self._publication_binding = publication_binding
        self._operations = operations
        self._registry = registry
        self._world = world
        self._players = players
        self._history = history
        self._contexts = SnapshotAttemptContextBuilder(registry=registry)
        self._dependencies = SnapshotPreparedDependencyValidator(fingerprints=SectionFingerprint(registry))
        self._request_codec = request_codec
        self._request_validator = SnapshotRequestValidator(request_codec)

    async def _admit_and_claim(self, request: PatchSet[S]) -> PublicationOwner | T:
        """Internal entry seam; a new owner still needs the full apply transaction."""
        try:
            checked = self._request_validator.validate(request)
        except (PatchSetValidationClassificationError, PublicationInfrastructureError) as error:
            raise SnapshotPublicError(SnapshotPublicFault(operation=SnapshotPublicOperation.APPLY,
                kind=SnapshotPublicFailureKind.INFRASTRUCTURE_FAILURE, operation_id=None,
                request_fingerprint=None, input_issues=())) from error
        try:
            request_fingerprint = self._request_codec.fingerprint(checked)
        except Exception as error:
            raise SnapshotPublicError(SnapshotPublicFault(operation=SnapshotPublicOperation.APPLY,
                kind=SnapshotPublicFailureKind.INFRASTRUCTURE_FAILURE, operation_id=None,
                request_fingerprint=None, input_issues=())) from error
        return await self._claim_publication(checked.operation_id, checked.world_uid,
            checked.preparation_fingerprint, request_fingerprint)

    async def _validate_sections(self, request: PatchSet[S], *, scope: CommitReadScope,
                                 resolved_dependencies: tuple[SectionDependency, ...]
                                 ) -> SnapshotValidationContext:
        """New-attempt phase, after claim/replay and expected/source binding checks."""
        scope.assert_active()
        dependency_issues = self._dependencies.validate(request)
        if dependency_issues:
            # Snapshot-owned diagnostics are not domain SectionRefused diagnostics.
            raise _SnapshotValidationRefused(SnapshotApplyOutcomeKind.REJECTED, dependency_issues)
        validation = self._contexts.build(request, scope=scope, resolved_dependencies=resolved_dependencies)
        diagnostics = ValidatorAggregationHelper((SnapshotApplyRelationIssue, *self._registry.diagnostic_types))
        categories = []
        for section in request.sections:
            self._contexts.assert_bound(validation, request=request, scope=scope)
            try:
                outcome = await self._registry.resolve(section).validate(section, validation)
            except SectionHandlerContractError as error:
                raise PublicationInfrastructureError("invalid handler validation output") from error
            if isinstance(outcome, SectionRefused):
                for issue in outcome.diagnostics:
                    diagnostics.add(issue)
                categories.append(outcome.category)
        if categories:
            category = (SnapshotApplyOutcomeKind.REJECTED if SnapshotApplyOutcomeKind.REJECTED in categories
                        else SnapshotApplyOutcomeKind.CONFLICT)
            raise _SnapshotValidationRefused(category, diagnostics.snapshot())
        return validation

    async def _claim_publication(self, operation_id: EntityUid,
                                 world_uid: EntityUid, preparation_fingerprint: RevisionHex,
                                 request_fingerprint: RevisionHex) -> PublicationOwner | T:
        """Resolve admission before target reads; the store owns its short transaction."""
        operation_id = TypeAdapter(EntityUid).validate_python(operation_id, strict=True)
        world_uid = TypeAdapter(EntityUid).validate_python(world_uid, strict=True)
        preparation_fingerprint = TypeAdapter(RevisionHex).validate_python(preparation_fingerprint, strict=True)
        request_fingerprint = TypeAdapter(RevisionHex).validate_python(request_fingerprint, strict=True)
        try:
            claim = await self._operations.claim_publication(OperationKind.SNAPSHOT_APPLY, operation_id, world_uid,
                                                       preparation_fingerprint, request_fingerprint)
        except OperationBindingMismatchError as error:
            mismatch = error.mismatch
            if (mismatch.operation_id != operation_id or mismatch.requested_kind is not OperationKind.SNAPSHOT_APPLY
                    or mismatch.requested_world_uid != world_uid
                    or mismatch.requested_preparation_fingerprint != preparation_fingerprint
                    or mismatch.requested_request_fingerprint != request_fingerprint):
                raise PublicationInfrastructureError("mismatch carrier describes another request") from error
            return self._publication_binding.result_model(category=SnapshotApplyOutcomeKind.REJECTED,
                operation_id=operation_id, request_fingerprint=request_fingerprint, committed=None,
                diagnostics=(SnapshotApplyRelationIssue(code=SnapshotApplyCode.OPERATION_BINDING_MISMATCH,
                                                        section_key=None, player_uid=None, artifact=None),))
        claim = TypeAdapter(OperationClaim[self._publication_binding.result_model]).validate_python(claim, strict=True)
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
        if type(record.terminal) is not self._publication_binding.result_model:
            raise PublicationInfrastructureError("snapshot operation has an unexpected terminal")
        return record.terminal

    async def _load_pinned_bases(
        self, validation: SnapshotValidationContext, *, scope: CommitReadScope,
        source_bases: Mapping[SnapshotRef, SnapshotEnvelope],
    ) -> Mapping[SnapshotRef, SnapshotEnvelope]:
        parents = ((None, validation.expected_world.snapshot_head),
                   *((i, head.expected_head) for i, head in enumerate(validation.expected_players)))
        bases: dict[SnapshotRef, SnapshotEnvelope] = {}
        missing = ValidatorAggregationHelper((MissingPersistedSnapshotBase,))
        visited: set[SnapshotRef] = set()
        adapter = TypeAdapter(SnapshotEnvelope)
        for player_index, ref in parents:
            if ref is None or ref in visited:
                continue
            visited.add(ref)
            scope.assert_active()
            try:
                metadata = source_bases[ref] if ref in source_bases else await self._history.read(ref, scope=scope)
                if metadata is None:
                    if ref in source_bases:
                        raise ValueError("cached base is not metadata")
                    missing.add(MissingPersistedSnapshotBase(snapshot=ref, player_index=player_index))
                    continue
                metadata = adapter.validate_python(metadata, strict=True)
                if metadata.ref != ref:
                    raise ValueError("pinned metadata identity mismatch")
                bases[ref] = metadata
            except PublicationInfrastructureError:
                raise
            except Exception as error:
                raise PublicationInfrastructureError("could not read exact pinned metadata") from error
        missing.raise_if_any(PublicationInfrastructureError)
        return MappingProxyType(bases)

    async def _append_metadata_and_handoff(
        self, context: SnapshotApplyContext, turn_id: int, created_at: CreatedAtUtc,
        receipts: tuple[SectionApplyReceipt, ...],
        *, bases: Mapping[SnapshotRef, SnapshotEnvelope],
        holders: IArtifactHolders, lease: OperationLeaseRef, transferred: tuple[ArtifactRef, ...],
    ) -> None:
        """Publish derived closures and transfer selected holds in the caller's writer scope."""
        await self._append_metadata(context, turn_id, created_at, receipts, bases=bases)
        await holders.handoff(context.scope, lease, (context.world_snapshot, *context.player_snapshots), transferred)

    async def _append_metadata(self, context: SnapshotApplyContext, turn_id: int, created_at: CreatedAtUtc,
                               receipts: tuple[SectionApplyReceipt, ...], *,
                               bases: Mapping[SnapshotRef, SnapshotEnvelope]) -> None:
        envelopes = SnapshotMetadataBuilder.build(context, turn_id, created_at, receipts, bases)
        for envelope in envelopes:
            await self._history.append(context.scope, envelope, receipts)

    @asynccontextmanager
    async def _apply_to_target(self, scope: CommitScope, validation: SnapshotValidationContext,
                               sections: tuple[DomainSection, ...], snapshot: WorldSnapshotRef,
                               players: tuple[PlayerSnapshotRef, ...], *,
                               bases: Mapping[SnapshotRef, SnapshotEnvelope], request: PatchSet[S],
                               ) -> AsyncIterator[tuple[SnapshotApplyContext, tuple[SectionApplyReceipt, ...]]]:
        """Apply validated sections, allow metadata and handoff, then CAS before outer commit."""
        expected = validation.expected_world
        if sections is not request.sections:
            raise PublicationInfrastructureError("apply sections differ from admitted request")
        self._contexts.assert_bound(validation, request=request, scope=scope.read_scope)
        base_issues = collect_pinned_base_issues(validation, bases)
        if base_issues:
            raise PublicationInfrastructureError(base_issues)
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
        for section_index, section in enumerate(sections):
            self._contexts.assert_bound(validation, request=request, scope=scope.read_scope)
            # SNAPSHOT-V1-BOUNDARY: deferred domains keep their v1 contracts.
            # This dispatch accepts registered native sections; it must not adapt
            # generator output or invoke a domain's public pipeline instead of DAG.
            # See .cursor/plans/snapshot-public-contracts-dag-integration.md, section 7.
            try:
                outcome = await self._registry.resolve(section).apply(section, context)
            except SectionHandlerContractError as error:
                raise PublicationInfrastructureError("invalid handler apply output") from error
            if isinstance(outcome, SectionRefused):
                raise _ApplyRefused(outcome)
            SnapshotReceiptValidator().validate(section, outcome, context, bases, section_index=section_index)
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
