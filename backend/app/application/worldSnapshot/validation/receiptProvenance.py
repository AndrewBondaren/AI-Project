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

    history = tuple(entry for receipt in receipts for entry in receipt.history if entry.history.snapshot == metadata.ref)
    if sorted(history, key=lambda entry: str(entry.history.section_key)) != sorted(
            metadata.history, key=lambda entry: str(entry.history.section_key)):
        raise ValueError("metadata history does not match section receipts")
    states = {entry.state.section_key: entry for entry in base.states} if base is not None else {}
    for receipt in receipts:
        for entry in receipt.history:
            if _same_owner(entry.history.snapshot, metadata.ref) and entry.history.snapshot != metadata.ref:
                raise ValueError("receipt history does not use the assigned snapshot")
        for entry in receipt.states:
            ref = entry.state
            if not _same_owner(ref.snapshot, metadata.ref):
                continue
            if ref.snapshot == metadata.ref:
                if not receipt.changed:
                    raise ValueError("no-op receipt cannot replace state")
                states[ref.section_key] = entry
            elif base is None or entry not in base.states:
                raise ValueError("inherited state closure differs from the pinned base")
    if sorted(states.values(), key=lambda entry: str(entry.state.section_key)) != sorted(
            metadata.states, key=lambda entry: str(entry.state.section_key)):
        raise ValueError("metadata state closure does not match receipts and pinned base")
    for receipt in receipts:
        for entry in receipt.states:
            if _same_owner(entry.state.snapshot, metadata.ref) and entry not in metadata.states:
                raise ValueError("receipt state is missing or superseded in metadata")
