"""Settings input fact delivery; handlers and routing belong to the logging facade."""

from app.core.logging.contracts import LogConsumer
from app.core.logging.consumers import get_consumer_logger
from collections.abc import Iterable
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.application.jsonValidation.resolution.diagnostics import ResolveContext
from app.application.jsonValidation.types import validate_import_issues, wire_loc
from app.dataModel.physics.settings.settingsInput import PhysicsGravityDefaultApplied
from app.dataModel.physics.settings.settingsIssues import PhysicsGravityArguments, PhysicsGravityCode, PhysicsGravityTypeError
from app.dataModel.physics.settings.worldPhysicsSettings import NonnegativeFinite
from app.dataModel.fields.validatedFieldPath import ValidatedFieldPath
from app.dataModel.validation.importIssues.jsonValidationCode import JsonValidationCode
from app.dataModel.validation.importIssues.wireLocation import WirePart
from app.dataModel.validation.importIssues.jsonFieldError import JsonFieldError
from app.dataModel.validation.importIssues.wireShapeIssue import WireShapeIssue

logger = get_consumer_logger(LogConsumer.PHYSICS_SETTINGS)
type InputIssue = PhysicsGravityTypeError | JsonFieldError | WireShapeIssue


class _InputEvent(BaseModel):
    """Application logging projection, not a new domain cause or collector."""

    model_config = ConfigDict(frozen=True, strict=True, extra="forbid")
    activity: Literal["physics_settings_input"] = "physics_settings_input"
    location: tuple[WirePart, ...]


class _ShapeEvent(_InputEvent):
    issue_type: Literal["WireShapeIssue"] = "WireShapeIssue"
    code: JsonValidationCode


class _FieldEvent(_InputEvent):
    issue_type: Literal["JsonFieldError"] = "JsonFieldError"
    code: JsonValidationCode
    path: ValidatedFieldPath


class _GravityEvent(_InputEvent):
    issue_type: Literal["PhysicsGravityTypeError"] = "PhysicsGravityTypeError"
    code: PhysicsGravityCode
    path: ValidatedFieldPath
    arguments: PhysicsGravityArguments


class _FallbackEvent(_GravityEvent):
    selected_default: NonnegativeFinite


def _emit(fact: InputIssue | PhysicsGravityDefaultApplied) -> None:
    event: _ShapeEvent | _FieldEvent | _GravityEvent | _FallbackEvent
    if isinstance(fact, PhysicsGravityDefaultApplied):
        issue = fact.cause
        event = _FallbackEvent(location=wire_loc(issue), code=issue.code,
                               path=issue.path, arguments=issue.arguments, selected_default=fact.selected)
    elif isinstance(fact, PhysicsGravityTypeError):
        event = _GravityEvent(location=wire_loc(fact), code=fact.code,
                              path=fact.path, arguments=fact.arguments)
    elif isinstance(fact, JsonFieldError):
        event = _FieldEvent(location=wire_loc(fact), code=fact.code, path=fact.path)
    else:
        event = _ShapeEvent(location=wire_loc(fact), code=fact.code)
    message = fact.cause.message if isinstance(fact, PhysicsGravityDefaultApplied) else fact.message
    # Only the logging boundary converts the closed projection to JSON-safe extra.
    logger.warning("physics_settings | WarningError | %s", message, extra=event.model_dump(mode="json"))


def report_issues(ctx: ResolveContext, issues: Iterable[InputIssue]) -> None:
    admitted = tuple(dict.fromkeys(issues))
    ctx.errors.extend(validate_import_issues(admitted))
    if not ctx.validate_only and not ctx.collect_only:
        for issue in admitted:
            _emit(issue)


def report_continuation(ctx: ResolveContext, diagnostic: PhysicsGravityDefaultApplied) -> None:
    if ctx.report.record_continuation(diagnostic.cause, same_wire_cause=False):
        if not ctx.validate_only and not ctx.collect_only:
            _emit(diagnostic)
