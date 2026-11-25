"""Time-owned native admission; preserves structural and independent field errors."""
from typing import Any
from pydantic import BaseModel, ValidationError, ModelWrapValidatorHandler
from pydantic_core import InitErrorDetails
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.fields.fieldRef import FieldRef

from app.dataModel.time.changes.admission import valid_field
from app.dataModel.validation.diagnostics.validatorAggregationHelper import ValidatorAggregationHelper
from app.dataModel.world.calendar.projection.errors import CalendarFieldIssue, CalendarIssueCode


def admit[M: BaseModel](model: type[M], value: object, handler: ModelWrapValidatorHandler[M],
                      checks: tuple[tuple[CheckedPath[M, Any], object, FieldRef[Any, Any], object], ...]) -> M:
    structural = []
    result = None
    try:
        result = handler(value)
    except ValidationError as error:
        structural = error.errors(include_url=False)
    errors = ValidatorAggregationHelper((CalendarFieldIssue,))
    inputs = {}
    for parent, owner, field, expected in checks:
        actual = valid_field(owner, field)
        if actual is not None and expected is not None and actual != expected:
            path = parent.field(field).freeze()
            inputs[path.projection()] = actual
            errors.add(CalendarFieldIssue(path=path, code=CalendarIssueCode.INVALID_SETTINGS_CHANGE,
                message="native settings header differs from its owning contract"))
    details = [*structural, *[
        InitErrorDetails(type="value_error", loc=issue.path.projection(), input=inputs[issue.path.projection()],
            ctx={"error": ValueError(issue.message)}) for issue in errors.snapshot()
    ]]
    if details:
        raise ValidationError.from_exception_data(model.__name__, details)
    assert result is not None
    return result
