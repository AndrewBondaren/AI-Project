"""Receipt/state provenance for assigned snapshots and a pinned base; no IO."""

from pydantic import TypeAdapter

from app.dataModel.identity.uid import EntityUid
from app.dataModel.patch.results.sectionResult import SectionApplyReceipt
from app.dataModel.worldSnapshot.identity.refs import SnapshotRef, WorldSnapshotRef, PlayerSnapshotRef
from app.dataModel.worldSnapshot.metadata.envelope import SnapshotEnvelope

_ENVELOPE = TypeAdapter(SnapshotEnvelope)
_RECEIPTS = TypeAdapter(tuple[SectionApplyReceipt, ...])
_UID = TypeAdapter(EntityUid)


def _same_owner(candidate: SnapshotRef, assigned: SnapshotRef) -> bool:
    return ((isinstance(candidate, WorldSnapshotRef) and isinstance(assigned, WorldSnapshotRef)
             and candidate.world_uid == assigned.world_uid) or
            (isinstance(candidate, PlayerSnapshotRef) and isinstance(assigned, PlayerSnapshotRef)
             and candidate.player_uid == assigned.player_uid))


def validate_receipt_provenance(metadata: SnapshotEnvelope, receipts: tuple[SectionApplyReceipt, ...],
                                base: SnapshotEnvelope | None, operation_id: EntityUid) -> None:
    metadata = _ENVELOPE.validate_python(metadata, strict=True)
    receipts = _RECEIPTS.validate_python(receipts, strict=True)
    base = None if base is None else _ENVELOPE.validate_python(base, strict=True)
    operation_id = _UID.validate_python(operation_id, strict=True)
    if metadata.operation_id != operation_id:
        raise ValueError("metadata belongs to another publication operation")
    if (None if base is None else base.ref) != metadata.parent:
        raise ValueError("base must be the exact pinned parent")
    if len({receipt.section_key for receipt in receipts}) != len(receipts):
        raise ValueError("duplicate section receipt")
    if any(patch.operation_id != operation_id for receipt in receipts for patch in receipt.changed):
        raise ValueError("receipt belongs to another operation")

    history = tuple(ref for receipt in receipts for ref in receipt.history_refs if ref.snapshot == metadata.ref)
    if sorted(history, key=lambda ref: str(ref.section_key)) != sorted(metadata.history_refs, key=lambda ref: str(ref.section_key)):
        raise ValueError("metadata history does not match section receipts")
    state = tuple(ref for receipt in receipts for ref in receipt.state_refs if ref.snapshot == metadata.ref)
    current = tuple(ref for ref in metadata.state_refs if ref.snapshot == metadata.ref)
    if sorted(state, key=lambda ref: str(ref.section_key)) != sorted(current, key=lambda ref: str(ref.section_key)):
        raise ValueError("new metadata state does not match section receipts")
    for receipt in receipts:
        if any(_same_owner(ref.snapshot, metadata.ref) and ref.snapshot != metadata.ref
               for ref in receipt.history_refs):
            raise ValueError("receipt history does not use the assigned snapshot")
        if any(_same_owner(ref.snapshot, metadata.ref) and ref not in metadata.state_refs
               for ref in receipt.state_refs):
            raise ValueError("receipt state is missing from the resulting metadata")
    if any(ref.snapshot != metadata.ref and (base is None or ref not in base.state_refs)
           for ref in metadata.state_refs):
        raise ValueError("retained section state is not reachable from the pinned base")
