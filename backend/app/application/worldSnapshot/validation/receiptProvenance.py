"""Receipt/state provenance for assigned snapshots and a pinned base; no IO."""

from collections.abc import Mapping
from pydantic import TypeAdapter

from app.application.worldSnapshot.contracts.context import SnapshotApplyContext, SnapshotValidationContext
from app.application.worldSnapshot.validation.receiptFacts import AdmittedState, ReceiptFacts, ReceiptFactsAdmission
from app.dataModel.fields.fieldBinding import bind_field
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.patch.changes.header import PatchRef
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper
from app.dataModel.worldSnapshot.metadata.metadataIssues import SnapshotMetadataCode as Code, SnapshotMetadataRelationIssue
from app.dataModel.worldSnapshot.sections.refs import SectionHistoryRef

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


def receipt_owner(ref: SnapshotRef, assigned: tuple[SnapshotRef, ...]) -> SnapshotRef | None:
    matches = tuple(target for target in assigned if _same_owner(ref, target))
    if len(matches) > 1:
        raise ValueError("duplicate assigned snapshot owner")
    return matches[0] if matches else None


def patch_matches_operation(ref: PatchRef, expected_operation_id: EntityUid) -> bool:
    return ref.operation_id == expected_operation_id


def history_uses_assigned(ref: SectionHistoryRef, assigned: SnapshotRef) -> bool:
    return ref.snapshot == assigned


def state_provenance_codes(state: AdmittedState, *, assigned: SnapshotRef,
                           base: SnapshotEnvelope | None, changed_empty: bool | None,
                           replaces_same_owner_section: bool, base_available: bool = True) -> tuple[Code, ...]:
    if not base_available and base is not None:
        raise ValueError("unavailable base cannot contain metadata")
    if state.ref.snapshot == assigned:
        return (Code.NOOP_STATE,) if changed_empty is True else ()
    codes = []
    if replaces_same_owner_section:
        codes.append(Code.SUPERSEDED_STATE)
    if base_available and (base is None or not any(entry.state == state.ref for entry in base.states)
                           or (state.retention is not None and state.retention not in base.states)):
        codes.append(Code.UNREACHABLE_STATE)
    return tuple(codes)


def collect_pinned_base_issues(validation: SnapshotValidationContext,
                               bases: Mapping[SnapshotRef, SnapshotEnvelope]) -> tuple[SnapshotMetadataRelationIssue, ...]:
    errors = ValidatorAggregationHelper((SnapshotMetadataRelationIssue,))
    pinned = tuple(ref for ref in (validation.expected_world.snapshot_head,
                                   *(head.expected_head for head in validation.expected_players)) if ref is not None)
    for ref in pinned:
        if ref not in bases:
            errors.add(SnapshotMetadataRelationIssue(code=Code.MISSING_BASE, location="bases",
                address=(ref.snapshot_id,), snapshot=ref, message="missing pinned snapshot"))
        elif bases[ref].ref != ref:
            name = bind_field(FieldRef(lambda: type(bases[ref]), lambda m: m.ref)).field
            errors.add(SnapshotMetadataRelationIssue(code=Code.BASE_IDENTITY, location="bases",
                address=(ref.snapshot_id, name), message="metadata base identity mismatch"))
    for ref in bases:
        if ref not in pinned:
            errors.add(SnapshotMetadataRelationIssue(code=Code.UNEXPECTED_BASE, location="bases",
                address=(ref.snapshot_id,), message="base is not pinned"))
    return errors.snapshot()


def _receipt_issue(facts: ReceiptFacts, code: Code, index: int) -> SnapshotMetadataRelationIssue:
    # These are relation addresses, not field-error paths.
    addresses = {
        Code.FOREIGN_HISTORY: ("history", index, "history", "snapshot"),
        Code.NOOP_STATE: ("states", index, "state", "snapshot"),
        Code.SUPERSEDED_STATE: ("states", index),
        Code.UNREACHABLE_STATE: ("states", index, "state", "snapshot"),
    }
    messages = {
        Code.FOREIGN_HISTORY: "history must target an assigned snapshot",
        Code.NOOP_STATE: "no-op receipt cannot replace state",
        Code.SUPERSEDED_STATE: "receipt also replaces this inherited state",
        Code.UNREACHABLE_STATE: "state closure is not reachable from pinned base",
    }
    return SnapshotMetadataRelationIssue(code=code, location="receipts",
        address=(facts.section_index, *addresses[code]), message=messages[code])


def collect_owned_receipt_provenance(facts: ReceiptFacts, assigned: SnapshotRef,
                                     base: SnapshotEnvelope | None, *, base_available: bool = True
                                     ) -> tuple[SnapshotMetadataRelationIssue, ...]:
    errors = ValidatorAggregationHelper((SnapshotMetadataRelationIssue,))
    for item in facts.history:
        if _same_owner(item.ref.snapshot, assigned) and not history_uses_assigned(item.ref, assigned):
            errors.add(_receipt_issue(facts, Code.FOREIGN_HISTORY, item.index))
    replacements = {item.ref.section_key for item in facts.states if item.ref.snapshot == assigned}
    for item in facts.states:
        if not _same_owner(item.ref.snapshot, assigned):
            continue
        for code in state_provenance_codes(item, assigned=assigned, base=base,
                changed_empty=facts.changed_empty, replaces_same_owner_section=item.ref.section_key in replacements,
                base_available=base_available):
            errors.add(_receipt_issue(facts, code, item.index))
    return errors.snapshot()


def collect_receipt_provenance(facts: ReceiptFacts, context: SnapshotApplyContext,
                               bases: Mapping[SnapshotRef, SnapshotEnvelope]) -> tuple[SnapshotMetadataRelationIssue, ...]:
    assigned = (context.world_snapshot, *context.player_snapshots)
    players = {head.player_uid: head.expected_head for head in context.validation.expected_players}
    parents = (context.validation.expected_world.snapshot_head,
               *(players.get(ref.player_uid) for ref in context.player_snapshots))
    owned: list[SnapshotMetadataRelationIssue] = []
    for target, parent in zip(assigned, parents, strict=True):
        available = parent is None or (parent in bases and bases[parent].ref == parent)
        base = bases[parent] if parent is not None and available else None
        owned.extend(collect_owned_receipt_provenance(facts, target, base, base_available=available))
    errors = ValidatorAggregationHelper((SnapshotMetadataRelationIssue,))
    for item in facts.history:
        if receipt_owner(item.ref.snapshot, assigned) is None:
            errors.add(_receipt_issue(facts, Code.FOREIGN_HISTORY, item.index))
        for issue in owned:
            if issue.code is Code.FOREIGN_HISTORY and issue.address[2] == item.index:
                errors.add(issue)
    for item in facts.states:
        if receipt_owner(item.ref.snapshot, assigned) is None:
            errors.add(_receipt_issue(facts, Code.UNREACHABLE_STATE, item.index))
        for issue in owned:
            if issue.code is not Code.FOREIGN_HISTORY and issue.address[2] == item.index:
                errors.add(issue)
    return errors.snapshot()


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
    if any(not patch_matches_operation(patch, operation_id) for receipt in receipts for patch in receipt.changed):
        raise ValueError("receipt belongs to another operation")

    history = tuple(entry for receipt in receipts for entry in receipt.history if entry.history.snapshot == metadata.ref)
    if sorted(history, key=lambda entry: str(entry.history.section_key)) != sorted(
            metadata.history, key=lambda entry: str(entry.history.section_key)):
        raise ValueError("metadata history does not match section receipts")
    states = {entry.state.section_key: entry for entry in base.states} if base is not None else {}
    facts = tuple(ReceiptFactsAdmission.admit(receipt, section_index=i) for i, receipt in enumerate(receipts))
    for receipt, admitted in zip(receipts, facts, strict=True):
        for entry in receipt.history:
            if _same_owner(entry.history.snapshot, metadata.ref) and not history_uses_assigned(entry.history, metadata.ref):
                raise ValueError("receipt history does not use the assigned snapshot")
        for item in admitted.states:
            ref = item.ref
            if not _same_owner(ref.snapshot, metadata.ref):
                continue
            codes = state_provenance_codes(item, assigned=metadata.ref, base=base,
                changed_empty=admitted.changed_empty, replaces_same_owner_section=False)
            if Code.NOOP_STATE in codes:
                raise ValueError("no-op receipt cannot replace state")
            if Code.UNREACHABLE_STATE in codes:
                raise ValueError("inherited state closure differs from the pinned base")
            if ref.snapshot == metadata.ref:
                states[ref.section_key] = item.retention
    if sorted(states.values(), key=lambda entry: str(entry.state.section_key)) != sorted(
            metadata.states, key=lambda entry: str(entry.state.section_key)):
        raise ValueError("metadata state closure does not match receipts and pinned base")
    for receipt in receipts:
        for entry in receipt.states:
            if _same_owner(entry.state.snapshot, metadata.ref) and entry not in metadata.states:
                raise ValueError("receipt state is missing or superseded in metadata")
