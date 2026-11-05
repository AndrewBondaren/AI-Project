"""Typed content admission; no publication pinning or default repair."""

from typing import get_args

from pydantic import BaseModel, TypeAdapter, ValidationError
from pydantic_core import InitErrorDetails
from pydantic_core.core_schema import ErrorType

from app.application.jsonValidation.resolution.diagnostics import ResolveContext
from app.application.jsonValidation.resolution.wireIssues import pydantic_issues
from app.application.jsonValidation.types import ImportIssue
from app.dataModel.fields.checkedPath import CheckedPath
from app.dataModel.identity.uid import EntityUid
from app.dataModel.physics.settings.settingsCapture import WorldPhysicsSettingsView, settings_ref
from app.dataModel.physics.settings.settingsIssues import (
    PhysicsSettingsAdmissionFailure, PhysicsSettingsSubject, SettingsContentMismatch,
    SettingsMalformedContract, SettingsSchemaMismatch, SettingsWorldMismatch,
)
from app.dataModel.physics.settings.worldPhysicsSettings import WorldPhysicsSettings
from app.dataModel.validation.immutableValue import validate_immutable
from app.dataModel.validation.importIssues.jsonFieldError import JsonFieldError
from app.dataModel.validation.importIssues.jsonValidationCode import JsonValidationCode
from app.dataModel.validation.importIssues.wireLocation import WireLocation
from app.dataModel.validation.importIssues.wireShapeIssue import WireShapeIssue

_ERROR_TYPES = frozenset(get_args(ErrorType))


class PhysicsSettingsBoundaryFault(RuntimeError):
    """Unrecognized mapper behavior, never a defaultable domain input."""


def malformed(subject: PhysicsSettingsSubject, message: str) -> PhysicsSettingsAdmissionFailure:
    return PhysicsSettingsAdmissionFailure(cause=SettingsMalformedContract(
        subject=subject, issues=(WireShapeIssue(
            code=JsonValidationCode.VALIDATION_ERROR, location=WireLocation(), message=message,
        ),),
    ))


def _structural_issues(issues: list[ImportIssue]) -> tuple[JsonFieldError | WireShapeIssue, ...]:
    admitted: list[JsonFieldError | WireShapeIssue] = []
    for issue in issues:
        if type(issue) not in (JsonFieldError, WireShapeIssue):
            raise PhysicsSettingsBoundaryFault("unexpected shared settings issue type")
        if isinstance(issue, (JsonFieldError, WireShapeIssue)):
            admitted.append(issue)
    return tuple(admitted)


def validation_failure(
    model: type[BaseModel] | None, exc: ValidationError, subject: PhysicsSettingsSubject,
) -> PhysicsSettingsAdmissionFailure:
    errors = exc.errors(include_input=False)
    if len(errors) == 1:
        error = errors[0]
        context = error.get("ctx", {})
        try:
            if error["type"] == "physics_settings_world":
                return PhysicsSettingsAdmissionFailure(cause=SettingsWorldMismatch.model_validate(context))
            if error["type"] == "physics_settings_schema":
                return PhysicsSettingsAdmissionFailure(cause=SettingsSchemaMismatch.model_validate(context))
            if error["type"] == "physics_settings_content":
                return PhysicsSettingsAdmissionFailure(cause=SettingsContentMismatch.model_validate(context))
        except ValidationError as mapper_error:
            raise PhysicsSettingsBoundaryFault("invalid Physics invariant arguments") from mapper_error
    # Unknown custom validator kinds must not fall through the generic mapper.
    if any(error["type"] not in _ERROR_TYPES and error["type"] != "physics_settings_immutable" for error in errors):
        raise PhysicsSettingsBoundaryFault("unmapped Physics settings validation code") from exc
    issues: list[JsonFieldError | WireShapeIssue] = []
    for error in exc.errors():
        if error["type"] == "physics_settings_immutable":
            issues.append(WireShapeIssue(
                code=JsonValidationCode.VALIDATION_ERROR,
                location=WireLocation(parts=error["loc"]), message="incomplete or invalid immutable settings",
            ))
        else:
            if (model is not None and error["loc"] and error["type"] not in ("extra_forbidden", "invalid_key")
                    and CheckedPath.from_pydantic_loc(model, error["loc"]) is None):
                raise PhysicsSettingsBoundaryFault("unmapped Physics settings validation path") from exc
            detail = InitErrorDetails(type=error["type"], loc=error["loc"], input=error["input"],
                                      ctx=error.get("ctx", {}))
            single = ValidationError.from_exception_data("settings", [detail])
            issues.extend(_structural_issues(pydantic_issues(ResolveContext(), model, single)))
    return PhysicsSettingsAdmissionFailure(cause=SettingsMalformedContract(subject=subject, issues=tuple(issues)))


def admit_record[RecordT: BaseModel](
    value: RecordT, model: type[RecordT], subject: PhysicsSettingsSubject,
) -> RecordT | PhysicsSettingsAdmissionFailure:
    if type(value) is not model:
        return malformed(subject, "unexpected settings record type")
    try:
        validate_immutable(value)
    except ValueError:
        return malformed(subject, "incomplete or invalid immutable settings record")
    try:
        return model.model_validate(value, strict=True)
    except ValidationError as exc:
        return validation_failure(model, exc, subject)


def build_settings_view(
    world_uid: EntityUid, settings: WorldPhysicsSettings,
) -> WorldPhysicsSettingsView | PhysicsSettingsAdmissionFailure:
    admitted = admit_record(settings, WorldPhysicsSettings, PhysicsSettingsSubject.SETTINGS)
    if isinstance(admitted, PhysicsSettingsAdmissionFailure):
        return admitted
    try:
        world_uid = TypeAdapter(EntityUid).validate_python(world_uid, strict=True)
    except ValidationError as exc:
        return validation_failure(None, exc, PhysicsSettingsSubject.VIEW)
    return WorldPhysicsSettingsView(settings=admitted, ref=settings_ref(world_uid, admitted))


def validate_settings_view(view: WorldPhysicsSettingsView) -> WorldPhysicsSettingsView | PhysicsSettingsAdmissionFailure:
    return admit_record(view, WorldPhysicsSettingsView, PhysicsSettingsSubject.VIEW)
