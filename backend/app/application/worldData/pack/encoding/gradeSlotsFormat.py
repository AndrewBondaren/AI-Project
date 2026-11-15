"""Strict bounded grade sidecar admission; storage preserves the original bytes."""

import json
from typing import TypeVar

from pydantic import BaseModel, ValidationError
from pydantic_core.core_schema import ErrorType

from app.application.artifacts.contracts.formatBackend import ArtifactFormatContract
from app.application.jsonValidation.resolution.diagnostics import ResolveContext
from app.application.jsonValidation.resolution.wireIssues import pydantic_issues
from app.application.worldData.pack.encoding.jsonDecodeBudget import JsonDecodeBudget, JsonDecodeLimitError
from app.application.worldData.pack.encoding.jsonDecodeErrors import JsonDecodeInputError
from app.dataModel.artifacts.references import ArtifactKind, FormatVersion
from app.dataModel.encoding.decodeLimits import DecodeLimits
from app.dataModel.fields.fieldBinding import bind_field
from app.dataModel.fields.fieldRef import FieldRef
from app.dataModel.terrain.relief.gradeSlot import GradeSlotSidecar, GradeCellSlots
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper, IssueAdmissionError
from app.dataModel.validation.importIssues.jsonFieldError import JsonFieldError
from app.dataModel.validation.importIssues.jsonValidationCode import JsonValidationCode
from app.dataModel.validation.importIssues.wireLocation import WireLocation
from app.dataModel.validation.importIssues.wireShapeIssue import WireShapeIssue
from app.dataModel.worldPack.meta.gradeSlotsStorageFormat import GRADE_SLOTS_FORMAT_KEY, GRADE_SLOTS_STORAGE_VERSION
from app.dataModel.worldPack.preparation.nestedAdmission import strict_metadata_record


class GradeSlotsValidationError(Exception):
    def __init__(self, issues: tuple[JsonFieldError | WireShapeIssue, ...]) -> None:
        self.issues = issues
        super().__init__("invalid grade slots payload")


class GradeSlotsFormatError(Exception):
    def __init__(self, format_version: FormatVersion) -> None:
        self.format_version = format_version
        super().__init__("unsupported grade slots format version")


_CELLS = bind_field(FieldRef(lambda: GradeSlotSidecar, lambda value: value.cells))
_SLOTS = bind_field(FieldRef(lambda: GradeCellSlots, lambda value: value.slots))
_X = bind_field(FieldRef(lambda: GradeCellSlots, lambda value: value.x))
_Y = bind_field(FieldRef(lambda: GradeCellSlots, lambda value: value.y))


RecordT = TypeVar("RecordT", bound=BaseModel)


def _shape(message: str, location: tuple[str | int, ...] = (), *, kind: ErrorType | None = None) -> WireShapeIssue:
    return WireShapeIssue(code=JsonValidationCode.SCHEMA_VIOLATION if kind else JsonValidationCode.VALIDATION_ERROR,
                          location=WireLocation(parts=location), message=message, pydantic_type=kind)


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise JsonDecodeInputError(_shape("duplicate JSON member", (key,)))
        result[key] = value
    return result


class GradeSlotsDecoder:
    def __init__(self, limits: DecodeLimits) -> None:
        JsonDecodeBudget(limits)
        self._limits = limits

    def decode(self, payload: bytes, format_version: FormatVersion) -> GradeSlotSidecar:
        if type(format_version) is not int or format_version != GRADE_SLOTS_STORAGE_VERSION:
            raise GradeSlotsFormatError(format_version)
        JsonDecodeBudget(self._limits).check(payload)
        try:
            parsed_json = json.loads(payload.decode("utf-8"), object_pairs_hook=_unique_object)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise JsonDecodeInputError(_shape("invalid UTF-8 JSON", kind="json_invalid")) from exc
        return self._validate(parsed_json, wire=True)

    def validate(self, value: GradeSlotSidecar) -> GradeSlotSidecar:
        return self._validate(value, wire=False)

    def _validate(self, value: object, *, wire: bool) -> GradeSlotSidecar:
        errors = ValidatorAggregationHelper[JsonFieldError | WireShapeIssue]((JsonFieldError, WireShapeIssue))

        def schema(model: type[RecordT], raw: object, location: tuple[str | int, ...] = ()) -> RecordT | None:
            try:
                return strict_metadata_record(model, raw)
            except ValidationError as exc:
                for issue in pydantic_issues(ResolveContext(collect_only=True, location=WireLocation(parts=location)), model, exc):
                    if not isinstance(issue, (JsonFieldError, WireShapeIssue)):
                        raise IssueAdmissionError("unexpected grade schema issue") from exc
                    errors.add(issue)
                return None

        raw = dict(vars(value)) if isinstance(value, GradeSlotSidecar) else value
        if not isinstance(raw, dict):
            errors.add(_shape("expected grade sidecar object", kind="model_type"))
            errors.raise_if_any(GradeSlotsValidationError)
        assert isinstance(raw, dict)
        raw = dict(raw)
        if wire and _CELLS.field not in raw:
            raw[_CELLS.field] = GradeSlotSidecar.model_fields[_CELLS.field].get_default(call_default_factory=True)
        rows = raw.get(_CELLS.field)
        container = list if wire else tuple
        # The owning omitted-field default is already a tuple.
        default_empty = wire and rows == ()
        checked_rows: list[GradeCellSlots] = []
        seen: set[tuple[int, int]] = set()
        if isinstance(rows, container) or default_empty:
            assert isinstance(rows, (list, tuple))
            if len(rows) > self._limits.max_items:
                raise JsonDecodeLimitError("grade cells item limit exceeded")
            for index, row in enumerate(rows):
                data = dict(vars(row)) if isinstance(row, GradeCellSlots) else row
                if isinstance(data, dict):
                    data = dict(data)
                    slots = data.get(_SLOTS.field)
                    if wire and isinstance(slots, list):
                        data[_SLOTS.field] = tuple(slots)
                    x, y = data.get(_X.field), data.get(_Y.field)
                    if type(x) is int and type(y) is int:
                        if (x, y) in seen:
                            errors.add(_shape("duplicate grade cell coordinates", (_CELLS.field, index)))
                        seen.add((x, y))
                checked = schema(GradeCellSlots, data, (_CELLS.field, index))
                if checked is not None:
                    checked_rows.append(checked)
            raw[_CELLS.field] = tuple(checked_rows)
        checked = schema(GradeSlotSidecar, raw)
        errors.raise_if_any(GradeSlotsValidationError)
        assert isinstance(checked, GradeSlotSidecar)
        return checked


def grade_slots_format(limits: DecodeLimits) -> ArtifactFormatContract[bytes]:
    decoder = GradeSlotsDecoder(limits)

    def encode(payload: bytes) -> bytes:
        decoder.decode(payload, GRADE_SLOTS_STORAGE_VERSION)
        return payload

    def decode(payload: bytes, version: FormatVersion) -> bytes:
        decoder.decode(payload, version)
        return payload

    return ArtifactFormatContract(key=GRADE_SLOTS_FORMAT_KEY, kind=ArtifactKind.BLOB,
        supported_versions=frozenset({GRADE_SLOTS_STORAGE_VERSION}), content_model=bytes, encode=encode, decode=decode)
