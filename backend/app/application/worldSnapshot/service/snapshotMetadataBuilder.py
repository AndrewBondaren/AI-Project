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
from app.dataModel.patch.changes.header import PatchRef
from app.dataModel.patch.results.sectionResult import SectionApplyReceipt
from app.dataModel.worldSnapshot.sections.refs import SectionHistoryRef, SectionStateRef
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


def metadata_field[M: BaseModel, T](model: M, select: Callable[[M], T]) -> tuple[str, T]:
    ref = FieldRef(lambda: type(model), select)
    return bind_field(ref).field, ref.select(model)


def _indexed_items[T: BaseModel](values: tuple[T, ...], model: type[T], *,
                                 validated: bool) -> tuple[tuple[int, T], ...]:
    if validated:
        return tuple(enumerate(values))
    # Whole-receipt validation already reported malformed items at their original paths.
    items: list[tuple[int, T]] = []
    if isinstance(values, tuple):
        for index, value in enumerate(values):
            try:
                items.append((index, model.model_validate(value, strict=True)))
            except ValidationError:
                continue
    return tuple(items)


def _owner(ref: SnapshotRef) -> tuple[str, str]:
    return ref.kind, ref.world_uid if isinstance(ref, WorldSnapshotRef) else ref.player_uid


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
        players = {}
        for i, head in enumerate(context.validation.expected_players):
            field, uid = metadata_field(head, lambda p: p.player_uid)
            if uid in players:
                report(("validation", "expected_players", i, field), "duplicate_expectation", "duplicate expected player")
            players[uid] = head.expected_head
        parents: dict[SnapshotRef, SnapshotRef | None] = {}
        parents[context.world_snapshot] = expected.snapshot_head
        assigned_uids = set()
        for i, player in enumerate(context.player_snapshots):
            field, uid = metadata_field(player, lambda p: p.player_uid)
            if uid not in players or uid in assigned_uids:
                report(("player_snapshots", i, field), "unexpected_player", "unmatched or duplicate assigned player")
            assigned_uids.add(uid)
            parents[player] = players.get(uid)
        for i, head in enumerate(context.validation.expected_players):
            field, uid = metadata_field(head, lambda p: p.player_uid)
            if uid not in assigned_uids:
                report(("validation", "expected_players", i, field), "missing_player", "missing assigned player")
        for ref, parent in parents.items():
            if ref == parent:
                report(("parents", ref.snapshot_id), "self_parent", "assigned snapshot cannot be its own parent")
        pinned = tuple(p for p in (expected.snapshot_head, *players.values()) if p is not None)
        for parent in pinned:
            if parent not in bases:
                report(("bases", parent.snapshot_id), "missing_base", "missing pinned snapshot")
            else:
                name, identity = metadata_field(bases[parent], lambda m: m.ref)
                if identity != parent:
                    report(("bases", parent.snapshot_id, name), "base_identity", "metadata base identity mismatch")
        for ref in bases:
            if ref not in pinned:
                report(("bases", ref.snapshot_id), "unexpected_base", "base is not pinned")
        artifacts: list[ArtifactRef] = []
        for ref, values in retained.items():
            if ref not in parents:
                report(("retained", ref.snapshot_id), "foreign_destination", "artifact destination is not assigned")
            if not isinstance(values, tuple):
                report(("retained", ref.snapshot_id), "invalid_retention", "retention must be a tuple")
                continue
            seen = set()
            for j, artifact in enumerate(values):
                try:
                    artifact = ArtifactRef.model_validate(artifact, strict=True)
                except ValidationError as error:
                    for issue in error.errors():
                        report(("retained", ref.snapshot_id, j, *issue["loc"]), "invalid_artifact", issue["msg"])
                    continue
                if artifact in seen:
                    report(("retained", ref.snapshot_id, j), "duplicate_artifact", "duplicate retained artifact")
                seen.add(artifact)
                if ref in parents:
                    artifacts.append(artifact)
        if not isinstance(receipts, tuple):
            report(("receipts",), "invalid_receipts", "receipts must be a tuple")
        validated: list[SectionApplyReceipt] = []
        seen_sections = set()
        for i, raw in enumerate(receipts if isinstance(receipts, tuple) else ()):
            path = ("receipts", i)
            invalid_fields = set()
            valid = True
            try:
                receipt = SectionApplyReceipt.model_validate(raw, strict=True)
            except ValidationError as error:
                valid = False
                for issue in error.errors():
                    loc = issue["loc"]
                    report((*path, *loc), "invalid_receipt", issue["msg"])
                    if loc and isinstance(loc[0], str):
                        invalid_fields.add(loc[0])
                if not isinstance(raw, SectionApplyReceipt):
                    continue
                missing_fields = {field: () for field in invalid_fields if not hasattr(raw, field)}
                receipt = raw.model_copy(update=missing_fields)
            else:
                validated.append(receipt)
            key_name, key = metadata_field(receipt, lambda r: r.section_key)
            if key_name not in invalid_fields:
                if key in seen_sections:
                    report((*path, key_name), "duplicate_section", "duplicate section receipt")
                seen_sections.add(key)
            changed_name, changed = metadata_field(receipt, lambda r: r.changed)
            for j, patch in _indexed_items(changed, PatchRef, validated=valid):
                op_name, op = metadata_field(patch, lambda p: p.operation_id)
                if op != context.validation.operation_id:
                    report((*path, changed_name, j, op_name), "foreign_operation", "patch belongs to another operation")
            name, refs = metadata_field(receipt, lambda r: r.retained_artifacts)
            for j, artifact in _indexed_items(refs, ArtifactRef, validated=valid):
                if artifact not in artifacts:
                    report((*path, name, j), "unassigned_artifact", "receipt artifact has no metadata destination")
            history_name, histories = metadata_field(receipt, lambda r: r.history_refs)
            for j, entry in _indexed_items(histories, SectionHistoryRef, validated=valid):
                field, snapshot = metadata_field(entry, lambda r: r.snapshot)
                if snapshot not in parents:
                    report((*path, history_name, j, field), "foreign_history", "history must target an assigned snapshot")
            state_name, states = metadata_field(receipt, lambda r: r.state_refs)
            indexed_states = _indexed_items(states, SectionStateRef, validated=valid)
            replacements = {(_owner(entry.snapshot), entry.section_key) for _, entry in indexed_states
                            if entry.snapshot in parents}
            for j, state_ref in indexed_states:
                field, snapshot = metadata_field(state_ref, lambda r: r.snapshot)
                if snapshot in parents:
                    if "changed" not in invalid_fields and not receipt.changed:
                        report((*path, state_name, j, field), "noop_state", "no-op receipt cannot replace state")
                else:
                    if isinstance(snapshot, WorldSnapshotRef):
                        owner_present = snapshot.world_uid == context.world_snapshot.world_uid
                        parent = expected.snapshot_head
                    else:
                        owner_present = snapshot.player_uid in players
                        parent = players.get(snapshot.player_uid)
                    if (_owner(snapshot), state_ref.section_key) in replacements:
                        report((*path, state_name, j), "superseded_state", "receipt also replaces this inherited state")
                    if owner_present and parent is not None and (parent not in bases or bases[parent].ref != parent):
                        continue  # Reachability depends on the pinned base.
                    if not owner_present or parent is None or state_ref not in bases[parent].state_refs:
                        report((*path, state_name, j, field), "unreachable_state", "state is not reachable from pinned base")
        field, pack = metadata_field(context.next_publication, lambda p: p.pack_hash)
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
