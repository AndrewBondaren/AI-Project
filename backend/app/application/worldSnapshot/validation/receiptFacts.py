"""Strict receipt admission with independently usable, originally indexed facts."""
from dataclasses import dataclass
from typing import Callable

from pydantic import BaseModel, TypeAdapter, ValidationError

from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldBinding import bind_field
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.patch.changes.header import PatchRef
from app.dataModel.patch.registry.sectionMetadata import SectionKey
from app.dataModel.patch.results.sectionResult import SectionApplyReceipt
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper
from app.dataModel.worldSnapshot.metadata.metadataIssues import (
    SnapshotBuilderIssue, SnapshotMetadataCode, SnapshotMetadataFieldIssue, SnapshotMetadataRelationIssue,
)
from app.dataModel.worldSnapshot.sections.refs import SectionHistoryRef, SectionStateRef
from app.dataModel.worldSnapshot.sections.retention import SectionHistoryRetention, SectionStateRetention


def check_receipt_index(index: int) -> None:
    if type(index) is not int:
        raise TypeError("receipt index must be an int")
    if index < 0:
        raise ValueError("receipt index must be nonnegative")


@dataclass(frozen=True, slots=True)
class AdmittedChanged:
    index: int
    ref: PatchRef

    def __post_init__(self) -> None:
        check_receipt_index(self.index)


@dataclass(frozen=True, slots=True)
class AdmittedState:
    index: int
    ref: SectionStateRef
    retention: SectionStateRetention | None

    def __post_init__(self) -> None:
        check_receipt_index(self.index)


@dataclass(frozen=True, slots=True)
class AdmittedHistory:
    index: int
    ref: SectionHistoryRef
    retention: SectionHistoryRetention | None

    def __post_init__(self) -> None:
        check_receipt_index(self.index)


@dataclass(frozen=True, slots=True)
class ReceiptFacts:
    section_index: int
    section_key: SectionKey | None
    changed_empty: bool | None
    changed: tuple[AdmittedChanged, ...]
    states: tuple[AdmittedState, ...]
    history: tuple[AdmittedHistory, ...]
    validated: SectionApplyReceipt | None
    structural_issues: tuple[SnapshotBuilderIssue, ...]

    def __post_init__(self) -> None:
        check_receipt_index(self.section_index)


def _raw_field[M: BaseModel, T](raw: object, model: type[M], select: Callable[[M], T]) -> object:
    field = bind_field(FieldRef(lambda: model, select)).field
    return raw.get(field) if isinstance(raw, dict) else getattr(raw, field, None)


def _admit[T](raw: object, adapter: TypeAdapter[T]) -> T | None:
    try:
        return adapter.validate_python(raw, strict=True)
    except ValidationError:
        return None


class ReceiptFactsAdmission:
    @staticmethod
    def admit(raw: object, *, section_index: int) -> ReceiptFacts:
        check_receipt_index(section_index)
        errors: ValidatorAggregationHelper[SnapshotBuilderIssue] = ValidatorAggregationHelper(
            (SnapshotMetadataFieldIssue, SnapshotMetadataRelationIssue))
        validated = None
        try:
            validated = SectionApplyReceipt.model_validate(raw, strict=True)
        except ValidationError as error:
            for issue in error.errors():
                loc = issue["loc"]
                path = CheckedPath.from_pydantic_loc(SectionApplyReceipt, loc)
                if path is None:
                    errors.add(SnapshotMetadataRelationIssue(code=SnapshotMetadataCode.INVALID_RECEIPT,
                        location="receipts", address=(section_index, *loc), message=issue["msg"]))
                else:
                    errors.add(SnapshotMetadataFieldIssue(code=SnapshotMetadataCode.INVALID_RECEIPT,
                        location="receipts", destination=(section_index,), path=path, message=issue["msg"]))
            if not isinstance(raw, SectionApplyReceipt):
                return ReceiptFacts(section_index, None, None, (), (), (), None, errors.snapshot())
        source = validated if validated is not None else raw
        key = _admit(_raw_field(source, SectionApplyReceipt, lambda r: r.section_key), TypeAdapter(SectionKey))
        raw_changed = _raw_field(source, SectionApplyReceipt, lambda r: r.changed)
        whole_changed = _admit(raw_changed, TypeAdapter(tuple[PatchRef, ...]))
        changed = []
        if isinstance(raw_changed, tuple):
            for index, item in enumerate(raw_changed):
                ref = _admit(item, TypeAdapter(PatchRef))
                if ref is not None:
                    changed.append(AdmittedChanged(index, ref))
        states = []
        raw_states = _raw_field(source, SectionApplyReceipt, lambda r: r.states)
        if isinstance(raw_states, tuple):
            for index, item in enumerate(raw_states):
                ref = _admit(_raw_field(item, SectionStateRetention, lambda r: r.state), TypeAdapter(SectionStateRef))
                if ref is not None:
                    states.append(AdmittedState(index, ref, _admit(item, TypeAdapter(SectionStateRetention))))
        histories = []
        raw_history = _raw_field(source, SectionApplyReceipt, lambda r: r.history)
        if isinstance(raw_history, tuple):
            for index, item in enumerate(raw_history):
                ref = _admit(_raw_field(item, SectionHistoryRetention, lambda r: r.history), TypeAdapter(SectionHistoryRef))
                if ref is not None:
                    histories.append(AdmittedHistory(index, ref, _admit(item, TypeAdapter(SectionHistoryRetention))))
        return ReceiptFacts(section_index, key, None if whole_changed is None else not whole_changed,
                            tuple(changed), tuple(states), tuple(histories), validated, errors.snapshot())
