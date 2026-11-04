"""Runtime tick application inside the publication owner's write transaction."""
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager

from app.core.validatorAggregationHelper import ValidatorAggregationHelper
from app.application.patch.registry.sectionRegistry import SectionRegistry
from app.application.worldSnapshot.contracts.commitScope import CommitScope
from app.application.worldSnapshot.contracts.context import SnapshotApplyContext, SnapshotValidationContext
from app.application.publication.errors import PublicationInfrastructureError
from app.application.worldSnapshot.service.snapshotMetadataBuilder import SnapshotMetadataBuilder, SnapshotMetadataFailure, metadata_field
from app.application.worldSnapshot.storage.historyStore import ISnapshotHistoryStore
from app.dataModel.worldSnapshot.metadata.envelope import CreatedAtUtc, SnapshotEnvelope
from app.dataModel.artifacts.references import ArtifactRef
from app.application.worldSnapshot.storage.publicationStore import IPlayerPublicationStore, IWorldPublicationStore
from app.dataModel.patch.results.sectionResult import SectionApplyReceipt, SectionRefused
from app.dataModel.patch.sections.section import DomainSection
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError
from app.dataModel.worldSnapshot.identity.publication import WorldPublicationRef
from app.dataModel.worldSnapshot.identity.refs import PlayerSnapshotRef, SnapshotRef, WorldSnapshotRef
from app.dataModel.worldSnapshot.results.outcomeKind import SnapshotApplyOutcomeKind
from app.dataModel.worldSnapshot.results.publication import CasDecision
from app.ids.deterministicIds import runtime_uid


class _ApplyRefused(Exception):
    """Propagate a domain refusal across the outer rollback boundary."""

    def __init__(self, refusal: SectionRefused) -> None:
        super().__init__(refusal.diagnostics)
        self.refusal = refusal


class WorldSnapshotService:
    def __init__(self, registry: SectionRegistry, world: IWorldPublicationStore, players: IPlayerPublicationStore,
                 history: ISnapshotHistoryStore) -> None:
        self._registry = registry
        self._world = world
        self._players = players
        self._history = history

    async def _append_metadata(self, context: SnapshotApplyContext, turn_id: int, created_at: CreatedAtUtc,
                               receipts: tuple[SectionApplyReceipt, ...],
                               retained: Mapping[SnapshotRef, tuple[ArtifactRef, ...]]) -> None:
        validation = context.validation
        field, world_parent = metadata_field(validation.expected_world, lambda p: p.snapshot_head)
        parents: list[tuple[tuple[str | int, ...], SnapshotRef | None]] = [
            (("validation", "expected_world", field), world_parent)]
        for i, head in enumerate(validation.expected_players):
            field, parent = metadata_field(head, lambda p: p.expected_head)
            parents.append((("validation", "expected_players", i, field), parent))
        bases: dict[SnapshotRef, SnapshotEnvelope] = {}
        missing: list[FieldPathError] = []
        for path, ref in parents:
            if ref is None:
                continue
            metadata = await self._history.read(ref, scope=context.scope.read_scope)
            if metadata is None:
                missing.append(FieldPathError(path, f"missing pinned snapshot {ref.snapshot_id}",
                                              code="snapshot.metadata.missing_persisted_base"))
            else:
                bases[ref] = metadata
        try:
            envelopes = SnapshotMetadataBuilder.build(context, turn_id, created_at, receipts, bases, retained)
        except SnapshotMetadataFailure as error:
            if not missing:
                raise
            errors = ValidatorAggregationHelper()
            for issue in (*missing, *error.diagnostics):
                if issue.code != "snapshot.metadata.missing_base":
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
            outcome = await self._registry.resolve(section).apply(section, context)
            if isinstance(outcome, SectionRefused):
                raise _ApplyRefused(outcome)
            if outcome.section_key != section.header.key:
                raise ValueError("receipt belongs to another section")
            receipts.append(outcome)
        yield context, tuple(receipts)
        if await self._world.compare_append(scope, expected, target) is CasDecision.MISMATCH:
            raise _ApplyRefused(SectionRefused(category=SnapshotApplyOutcomeKind.CONFLICT,
                diagnostics=(FieldPathError(path=(), message="world publication changed"),)))
        for head in validation.expected_players:
            decision = await self._players.compare_append(scope, head, assigned_players[head.player_uid],
                                                          validation.operation_id)
            if decision is CasDecision.MISMATCH:
                raise _ApplyRefused(SectionRefused(category=SnapshotApplyOutcomeKind.CONFLICT,
                    diagnostics=(FieldPathError(path=("expected_players", head.player_uid),
                                                message="player publication changed"),)))
