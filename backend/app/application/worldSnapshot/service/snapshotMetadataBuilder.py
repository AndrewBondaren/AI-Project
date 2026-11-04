"""Build immutable tick metadata from pinned envelopes and assigned participants."""
from collections.abc import Callable, Mapping
from typing import Annotated

from pydantic import BaseModel, Field, StrictInt, TypeAdapter, ValidationError

from app.core.validatorAggregationHelper import ValidatorAggregationHelper
from app.dataModel.cascade.cascadeGraph import bind_field
from app.dataModel.cascade.cascadeSpec import FieldRef
from app.dataModel.validation.diagnostics.fieldPathError import FieldPathError

from app.application.worldSnapshot.contracts.context import SnapshotApplyContext
from app.application.worldSnapshot.validation.receiptProvenance import validate_receipt_provenance
from app.dataModel.artifacts.references import ArtifactRef
from app.dataModel.patch.results.sectionResult import SectionApplyReceipt
from app.dataModel.worldSnapshot.identity.refs import SnapshotRef, WorldSnapshotRef
from app.dataModel.worldSnapshot.metadata.envelope import (
    CreatedAtUtc, PlayerSnapshotMetadata, SnapshotEnvelope, WorldSnapshotMetadata,
)

_TURN = TypeAdapter(Annotated[StrictInt, Field(ge=1)])
_CREATED = TypeAdapter(CreatedAtUtc)


class SnapshotMetadataFailure(ValueError):
    def __init__(self, diagnostics: tuple[FieldPathError, ...]) -> None:
        self.diagnostics = diagnostics
        super().__init__(diagnostics)


def _field[M: BaseModel, T](model: M, select: Callable[[M], T]) -> tuple[str, T]:
    ref = FieldRef(lambda: type(model), select)
    return bind_field(ref).field, ref.select(model)



class SnapshotMetadataBuilder:
    @staticmethod
    def build(context: SnapshotApplyContext, turn_id: int, created_at: CreatedAtUtc,
              receipts: tuple[SectionApplyReceipt, ...], bases: Mapping[SnapshotRef, SnapshotEnvelope],
              retained: Mapping[SnapshotRef, tuple[ArtifactRef, ...]]) -> tuple[SnapshotEnvelope, ...]:
        """Retention destinations are explicit; a flat receipt does not identify a holder."""
        errors = ValidatorAggregationHelper()
        def report(path: tuple[str | int, ...], code: str, message: str) -> None:
            errors.add(FieldPathError(path, message, code="snapshot.metadata." + code))

        for label, adapter, value in (("turn_id", _TURN, turn_id), ("created_at", _CREATED, created_at)):
            try:
                adapter.validate_python(value, strict=True)
            except ValidationError as error:
                report((label,), "invalid_" + label, error.errors()[0]["msg"])
        expected = context.validation.expected_world
        players = {p.player_uid: p.expected_head for p in context.validation.expected_players}
        assigned = (context.world_snapshot, *context.player_snapshots)
        parents = {ref: expected.snapshot_head if isinstance(ref, WorldSnapshotRef) else players[ref.player_uid]
                   for ref in assigned}
        pinned = tuple(parent for parent in parents.values() if parent is not None)
        for parent in pinned:
            if parent not in bases:
                report(("bases", parent.snapshot_id), "missing_base", "missing pinned snapshot")
            else:
                name, identity = _field(bases[parent], lambda m: m.ref)
                if identity != parent:
                    report(("bases", parent.snapshot_id, name), "base_identity", "metadata base identity mismatch")
        for ref in bases:
            if ref not in pinned:
                report(("bases", ref.snapshot_id), "unexpected_base", "base is not pinned")
        for ref in retained:
            if ref not in parents:
                report(("retained", ref.snapshot_id), "foreign_destination", "artifact destination is not assigned")
        artifacts = tuple(artifact for ref, refs in retained.items() if ref in parents for artifact in refs)
        if not isinstance(receipts, tuple):
            report(("receipts",), "invalid_receipts", "receipts must be a tuple")
        validated: list[SectionApplyReceipt] = []
        seen_sections = set()
        for i, raw in enumerate(receipts if isinstance(receipts, tuple) else ()):
            path = ("receipts", i)
            try:
                receipt = SectionApplyReceipt.model_validate(raw, strict=True)
            except ValidationError as error:
                for issue in error.errors():
                    report((*path, *issue["loc"]), "invalid_receipt", issue["msg"])
                continue
            validated.append(receipt)
            key_name, key = _field(receipt, lambda r: r.section_key)
            if key in seen_sections:
                report((*path, key_name), "duplicate_section", "duplicate section receipt")
            seen_sections.add(key)
            changed_name, changed = _field(receipt, lambda r: r.changed)
            for j, patch in enumerate(changed):
                op_name, op = _field(patch, lambda p: p.operation_id)
                if op != context.validation.operation_id:
                    report((*path, changed_name, j, op_name), "foreign_operation", "patch belongs to another operation")
            name, refs = _field(receipt, lambda r: r.retained_artifacts)
            for j, artifact in enumerate(refs):
                if artifact not in artifacts:
                    report((*path, name, j), "unassigned_artifact", "receipt artifact has no metadata destination")
            history_name, histories = _field(receipt, lambda r: r.history_refs)
            for j, entry in enumerate(histories):
                field, snapshot = _field(entry, lambda r: r.snapshot)
                if snapshot not in parents:
                    report((*path, history_name, j, field), "foreign_history", "history must target an assigned snapshot")
            state_name, states = _field(receipt, lambda r: r.state_refs)
            for j, state_ref in enumerate(states):
                field, snapshot = _field(state_ref, lambda r: r.snapshot)
                if snapshot in parents:
                    if not receipt.changed:
                        report((*path, state_name, j, field), "noop_state", "no-op receipt cannot replace state")
                else:
                    if isinstance(snapshot, WorldSnapshotRef):
                        owner_present = snapshot.world_uid == context.world_snapshot.world_uid
                        parent = expected.snapshot_head
                    else:
                        owner_present = snapshot.player_uid in players
                        parent = players.get(snapshot.player_uid)
                    if owner_present and parent is not None and (parent not in bases or bases[parent].ref != parent):
                        continue  # The diagnostic for this missing/invalid base already identifies the cause.
                    if not owner_present or parent is None or state_ref not in bases[parent].state_refs:
                        report((*path, state_name, j, field), "unreachable_state", "state is not reachable from pinned base")
        field, pack = _field(context.next_publication, lambda p: p.pack_hash)
        if pack is None:
            report(("context", "next_publication", field), "missing_pack", "runtime metadata requires a pack")
        errors.raise_if_any(SnapshotMetadataFailure)
        receipts = tuple(validated)
        assert pack is not None
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
