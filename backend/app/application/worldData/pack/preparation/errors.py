"""Application exception carrying the Pack-owned preparation refusal."""

from typing import TypeVar

from pydantic import BaseModel, ValidationError

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
)

InputT = TypeVar("InputT", bound=BaseModel)


class PackPreparationFailure(Exception):
    def __init__(self, error: PackPreparationError) -> None:
        self.error = PackPreparationError.model_validate(error, strict=True)
        super().__init__(self.error.reason.value)


def preparation_errors() -> ValidatorAggregationHelper[PackPreparationDiagnostic]:
    """Create the shared collector for one Pack admission stage."""
    return ValidatorAggregationHelper[PackPreparationDiagnostic](
        (JsonFieldError, WireShapeIssue, PackPreparationIssue)
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
    effective_reason = (
        PackPreparationFailureReason.INVALID_INPUT
        if any(type(issue) in (JsonFieldError, WireShapeIssue) for issue in errors.snapshot())
        else reason
    )
    errors.raise_if_any(lambda issues: PackPreparationFailure(
        PackPreparationError(reason=effective_reason, issues=issues)
    ))
