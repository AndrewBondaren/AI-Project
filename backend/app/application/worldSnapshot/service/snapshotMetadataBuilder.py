"""Build immutable tick metadata from pinned envelopes and assigned participants."""
from collections.abc import Mapping

from pydantic import TypeAdapter

from app.application.worldSnapshot.contracts.context import SnapshotApplyContext
from app.application.worldSnapshot.validation.receiptProvenance import validate_receipt_provenance
from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.patch.results.sectionResult import SectionApplyReceipt
from app.dataModel.worldSnapshot.identity.refs import SnapshotRef, WorldSnapshotRef
from app.dataModel.worldSnapshot.metadata.envelope import (
    CreatedAtUtc, PlayerSnapshotMetadata, SnapshotEnvelope, WorldSnapshotMetadata,
)

_RECEIPTS = TypeAdapter(tuple[SectionApplyReceipt, ...])


class SnapshotMetadataBuilder:
    @staticmethod
    def build(context: SnapshotApplyContext, turn_id: int, created_at: CreatedAtUtc,
              receipts: tuple[SectionApplyReceipt, ...], bases: Mapping[SnapshotRef, SnapshotEnvelope],
              retained: Mapping[SnapshotRef, tuple[ArtifactRef, ...]]) -> tuple[SnapshotEnvelope, ...]:
        """Retention destinations are explicit; a flat receipt does not identify a holder."""
        receipts = _RECEIPTS.validate_python(receipts, strict=True)
        expected = context.validation.expected_world
        players = {p.player_uid: p.expected_head for p in context.validation.expected_players}
        assigned = (context.world_snapshot, *context.player_snapshots)
        parents = {ref: expected.snapshot_head if isinstance(ref, WorldSnapshotRef) else players[ref.player_uid]
                   for ref in assigned}
        pinned = tuple(parent for parent in parents.values() if parent is not None)
        if any(parent not in bases for parent in pinned) or any(ref not in pinned for ref in bases):
            raise ValueError("metadata requires exactly the pinned bases")
        if retained.keys() - parents.keys():
            raise ValueError("artifact destination is not assigned")
        artifacts = tuple(artifact for refs in retained.values() for artifact in refs)
        if any(artifact not in artifacts for receipt in receipts for artifact in receipt.retained_artifacts):
            raise ValueError("receipt artifact has no metadata destination")
        for parent in pinned:
            if bases[parent].ref != parent:
                raise ValueError("metadata base identity mismatch")
        for receipt in receipts:
            if any(entry.snapshot not in parents for entry in receipt.history_refs):
                raise ValueError("receipt history must target an assigned snapshot")
            for entry in receipt.state_refs:
                if entry.snapshot in parents:
                    if not receipt.changed:
                        raise ValueError("no-op receipt cannot replace section state")
                elif not any(entry in base.state_refs for base in bases.values()):
                    raise ValueError("receipt state is not reachable from a pinned base")

        pack = context.next_publication.pack_hash
        if pack is None:
            raise ValueError("runtime metadata requires a pack")
        envelopes: list[SnapshotEnvelope] = []
        for ref, parent in parents.items():
            base = bases[parent] if parent is not None else None
            state = {entry.section_key: entry for entry in base.state_refs} if base else {}
            state.update((entry.section_key, entry) for receipt in receipts for entry in receipt.state_refs
                         if entry.snapshot == ref)
            history = tuple(entry for receipt in receipts for entry in receipt.history_refs if entry.snapshot == ref)
            if isinstance(ref, WorldSnapshotRef):
                metadata: SnapshotEnvelope = WorldSnapshotMetadata(ref=ref, parent=expected.snapshot_head,
                    operation_id=context.validation.operation_id, turn_id=turn_id, created_at=created_at,
                    envelope_format_version=1, base_pack_hash=pack,
                    state_refs=tuple(state.values()), history_refs=history, retained_artifacts=retained.get(ref, ()))
            else:
                metadata = PlayerSnapshotMetadata(ref=ref, parent=players[ref.player_uid],
                    operation_id=context.validation.operation_id, turn_id=turn_id, created_at=created_at,
                    envelope_format_version=1, state_refs=tuple(state.values()), history_refs=history,
                    retained_artifacts=retained.get(ref, ()))
            validate_receipt_provenance(metadata, receipts, base, context.validation.operation_id)
            envelopes.append(metadata)
        return tuple(envelopes)
