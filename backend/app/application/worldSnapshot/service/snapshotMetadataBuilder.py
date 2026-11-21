"""Build immutable tick metadata from pinned envelopes and assigned participants."""
from collections.abc import Callable, Mapping
from typing import Annotated

from pydantic import BaseModel, Field, StrictInt, TypeAdapter, ValidationError

from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper
from app.dataModel.fields.fieldBinding import bind_field
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.worldSnapshot.metadata.metadataIssues import (
    SnapshotBuilderIssue, SnapshotMetadataCode as Code, SnapshotMetadataFieldIssue, SnapshotMetadataRelationIssue,
)

from app.application.worldSnapshot.contracts.context import SnapshotApplyContext
from app.application.worldSnapshot.validation.receiptProvenance import (
    validate_receipt_provenance, collect_pinned_base_issues, collect_receipt_provenance, patch_matches_operation,
)
from app.application.worldSnapshot.validation.receiptFacts import ReceiptFactsAdmission
from app.dataModel.patch.results.sectionResult import SectionApplyReceipt
from app.dataModel.worldSnapshot.identity.refs import SnapshotRef, WorldSnapshotRef
from app.dataModel.worldSnapshot.metadata.envelope import (
    CreatedAtUtc, PlayerSnapshotMetadata, SnapshotEnvelope, WorldSnapshotMetadata,
)

_TURN = TypeAdapter(Annotated[StrictInt, Field(ge=1)])
_CREATED = TypeAdapter(CreatedAtUtc)


class SnapshotMetadataFailure(ValueError):
    def __init__(self, diagnostics: tuple[SnapshotBuilderIssue, ...]) -> None:
        self.diagnostics = diagnostics
        super().__init__(diagnostics)


def metadata_field[M: BaseModel, T](model: M, select: Callable[[M], T]) -> tuple[str, T]:
    ref = FieldRef(lambda: type(model), select)
    return bind_field(ref).field, ref.select(model)


class SnapshotMetadataBuilder:
    @staticmethod
    def build(context: SnapshotApplyContext, turn_id: int, created_at: CreatedAtUtc,
              receipts: tuple[SectionApplyReceipt, ...], bases: Mapping[SnapshotRef, SnapshotEnvelope]) -> tuple[SnapshotEnvelope, ...]:
        """Inherit exact closures and replace only the assigned owner/section."""
        errors: ValidatorAggregationHelper[SnapshotBuilderIssue] = ValidatorAggregationHelper(
            (SnapshotMetadataFieldIssue, SnapshotMetadataRelationIssue))

        def report(path: tuple[str | int, ...], code: Code, message: str, snapshot: SnapshotRef | None = None) -> None:
            errors.add(SnapshotMetadataRelationIssue.model_validate(dict(location=path[0], address=path[1:],
                code=code, message=message, snapshot=snapshot), strict=True))

        for label, adapter, value, code in (("turn_id", _TURN, turn_id, Code.INVALID_TURN_ID),
                                            ("created_at", _CREATED, created_at, Code.INVALID_CREATED_AT)):
            try:
                adapter.validate_python(value, strict=True)
            except ValidationError as error:
                for issue in error.errors():
                    report((label,), code, issue["msg"])
        expected = context.validation.expected_world
        players = {}
        for i, head in enumerate(context.validation.expected_players):
            field, uid = metadata_field(head, lambda p: p.player_uid)
            if uid in players:
                report(("validation", "expected_players", i, field), Code.DUPLICATE_EXPECTATION, "duplicate expected player")
            players[uid] = head.expected_head
        parents: dict[SnapshotRef, SnapshotRef | None] = {}
        parents[context.world_snapshot] = expected.snapshot_head
        assigned_uids = set()
        for i, player in enumerate(context.player_snapshots):
            field, uid = metadata_field(player, lambda p: p.player_uid)
            if uid not in players or uid in assigned_uids:
                report(("player_snapshots", i, field), Code.UNEXPECTED_PLAYER, "unmatched or duplicate assigned player")
            assigned_uids.add(uid)
            parents[player] = players.get(uid)
        for i, head in enumerate(context.validation.expected_players):
            field, uid = metadata_field(head, lambda p: p.player_uid)
            if uid not in assigned_uids:
                report(("validation", "expected_players", i, field), Code.MISSING_PLAYER, "missing assigned player")
        for ref, parent in parents.items():
            if ref == parent:
                report(("parents", ref.snapshot_id), Code.SELF_PARENT, "assigned snapshot cannot be its own parent")
        for issue in collect_pinned_base_issues(context.validation, bases):
            errors.add(issue)
        if not isinstance(receipts, tuple):
            report(("receipts",), Code.INVALID_RECEIPTS, "receipts must be a tuple")
        validated: list[SectionApplyReceipt] = []
        seen_sections = set()
        for i, raw in enumerate(receipts if isinstance(receipts, tuple) else ()):
            path = ("receipts", i)
            facts = ReceiptFactsAdmission.admit(raw, section_index=i)
            for issue in facts.structural_issues:
                errors.add(issue)
            if facts.validated is not None:
                validated.append(facts.validated)
            if facts.section_key is not None:
                if facts.section_key in seen_sections:
                    report((*path, "section_key"), Code.DUPLICATE_SECTION, "duplicate section receipt")
                seen_sections.add(facts.section_key)
            for item in facts.changed:
                if not patch_matches_operation(item.ref, context.validation.operation_id):
                    report((*path, "changed", item.index, "operation_id"), Code.FOREIGN_OPERATION,
                           "patch belongs to another operation")
            for issue in collect_receipt_provenance(facts, context, bases):
                errors.add(issue)
        field, pack = metadata_field(context.next_publication, lambda p: p.pack_hash)
        if pack is None:
            report(("context", "next_publication", field), Code.MISSING_PACK, "runtime metadata requires a pack")
        errors.raise_if_any(SnapshotMetadataFailure)
        receipts = tuple(validated)
        assert pack is not None
        envelopes: list[SnapshotEnvelope] = []
        for ref, parent in parents.items():
            base = bases[parent] if parent is not None else None
            state = {entry.state.section_key: entry for entry in base.states} if base else {}
            state.update((entry.state.section_key, entry) for receipt in receipts for entry in receipt.states
                         if entry.state.snapshot == ref)
            history = tuple(entry for receipt in receipts for entry in receipt.history if entry.history.snapshot == ref)
            if isinstance(ref, WorldSnapshotRef):
                metadata: SnapshotEnvelope = WorldSnapshotMetadata(ref=ref, parent=expected.snapshot_head,
                    operation_id=context.validation.operation_id, turn_id=turn_id, created_at=created_at,
                    envelope_format_version=1, base_pack_hash=pack,
                    states=tuple(state.values()), history=history)
            else:
                metadata = PlayerSnapshotMetadata(ref=ref, parent=players[ref.player_uid],
                    operation_id=context.validation.operation_id, turn_id=turn_id, created_at=created_at,
                    envelope_format_version=1, states=tuple(state.values()), history=history)
            validate_receipt_provenance(metadata, receipts, base, context.validation.operation_id)
            envelopes.append(metadata)
        return tuple(envelopes)
