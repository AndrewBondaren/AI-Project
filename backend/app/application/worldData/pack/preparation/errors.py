"""Application exception carrying the Pack-owned preparation refusal."""

from typing import TypeVar, get_args

from pydantic import BaseModel, TypeAdapter, ValidationError
from app.dataModel.fields.fieldBinding import bind_field
from app.dataModel.fields.fieldRef import FieldRef

from app.application.jsonValidation.resolution.diagnostics import ResolveContext
from app.application.jsonValidation.resolution.wireIssues import pydantic_issues
from app.dataModel.validation.diagnostics.validatorAggregationHelper import (
    IssueAdmissionError,
    ValidatorAggregationHelper,
)
from app.dataModel.validation.importIssues.jsonFieldError import JsonFieldError
from app.dataModel.validation.importIssues.wireShapeIssue import WireShapeIssue
from app.dataModel.worldPack.preparation.errors import (
    PackPreparationDiagnostic,
    PackPreparationError,
    PackPreparationFailureReason,
    PackPreparationIssue,
    PackPreparationArtifactIssue,
    PackPreparationRetentionLimitIssue,
    is_structural_preparation_issue,
)

InputT = TypeVar("InputT", bound=BaseModel)
ValueT = TypeVar("ValueT")
_MISSING_PREPARATION_FIELD = object()


def preparation_field_value(value: object, ref: FieldRef[InputT, ValueT]) -> object:
    """Preserve missing fields separately from explicit nullable values."""
    binding = bind_field(ref)
    if isinstance(value, binding.model):
        return vars(value).get(binding.field, _MISSING_PREPARATION_FIELD)
    if isinstance(value, dict):
        return value.get(binding.field, _MISSING_PREPARATION_FIELD)
    return _MISSING_PREPARATION_FIELD


def valid_preparation_field(value: object, ref: FieldRef[InputT, ValueT]) -> ValueT | None:
    """Validate one independent branch after root diagnostics have been collected."""
    binding = bind_field(ref)
    try:
        return TypeAdapter[ValueT](binding.model.model_fields[binding.field].rebuild_annotation()).validate_python(
            preparation_field_value(value, ref), strict=True)
    except ValidationError:
        return None


def valid_preparation_items(value: object, ref: FieldRef[InputT, tuple[ValueT, ...]]) -> tuple[tuple[int, ValueT], ...]:
    """Keep valid tuple elements and their original indices after schema admission."""
    binding = bind_field(ref)
    raw = preparation_field_value(value, ref)
    if not isinstance(raw, tuple):
        return ()
    annotation = binding.model.model_fields[binding.field].annotation
    adapter = TypeAdapter[ValueT](get_args(annotation)[0])
    accepted: list[tuple[int, ValueT]] = []
    for index, item in enumerate(raw):
        try:
            accepted.append((index, adapter.validate_python(item, strict=True)))
        except ValidationError:
            continue
    return tuple(accepted)


class PackPreparationFailure(Exception):
    def __init__(self, error: PackPreparationError) -> None:
        self.error = PackPreparationError.model_validate(error, strict=True)
        super().__init__(self.error.reason.value)


def preparation_errors() -> ValidatorAggregationHelper[PackPreparationDiagnostic]:
    """Create the shared collector for one Pack admission stage."""
    return ValidatorAggregationHelper[PackPreparationDiagnostic](
        (JsonFieldError, WireShapeIssue, PackPreparationIssue,
         PackPreparationArtifactIssue, PackPreparationRetentionLimitIssue)
    )


def validate_preparation_input(
    model: type[InputT], value: InputT,
    errors: ValidatorAggregationHelper[PackPreparationDiagnostic],
) -> InputT | None:
    """Internal schema admission; callers continue independent semantic checks."""
    try:
        return model.model_validate(value, strict=True)
    except ValidationError as exc:
        for issue in pydantic_issues(ResolveContext(collect_only=True), model, exc):
            if type(issue) not in (JsonFieldError, WireShapeIssue):
                raise IssueAdmissionError("unexpected Pack schema diagnostic class") from exc
            if isinstance(issue, (JsonFieldError, WireShapeIssue)):
                errors.add(issue)
        return None


def raise_preparation_errors(
    errors: ValidatorAggregationHelper[PackPreparationDiagnostic],
    reason: PackPreparationFailureReason,
) -> None:
    issues = errors.snapshot()
    if any(isinstance(issue, PackPreparationRetentionLimitIssue) for issue in issues):
        effective_reason = PackPreparationFailureReason.RESOURCE_LIMIT
    elif any(is_structural_preparation_issue(issue) for issue in issues):
        effective_reason = PackPreparationFailureReason.INVALID_INPUT
    else:
        effective_reason = reason
    errors.raise_if_any(lambda issues: PackPreparationFailure(
        PackPreparationError(reason=effective_reason, issues=issues)
    ))
