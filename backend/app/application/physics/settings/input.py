"""Fixed validation/runtime authoring operations, before strict settings/capture."""

from dataclasses import replace

from pydantic import ValidationError

from app.application.jsonValidation.resolution.diagnostics import (
    ResolveContext, ResolveMode, report_continuation, report_issues,
)
from app.application.jsonValidation.resolution.wireIssues import field_issue
from app.application.physics.settings.capture import PhysicsSettingsBoundaryFault
from app.dataModel.physics.settings.settingsInput import (
    PhysicsGravityDefaultApplied, PhysicsSettingsInputRefused, PhysicsSettingsInputResolved,
)
from app.dataModel.physics.settings.settingsIssues import (
    GRAVITY_PATH, PhysicsGravityArguments, PhysicsGravityCode, PhysicsGravityTypeError,
    PhysicsSettingsAdmissionFailure, PhysicsSettingsContextMode, PhysicsSettingsInputOperation,
    SettingsPolicyMismatch,
)
from app.dataModel.physics.settings.worldPhysicsSettings import STANDARD_GRAVITY_M_S2, WorldPhysicsSettings
from app.dataModel.validation.importIssues.jsonFieldError import JsonFieldError
from app.dataModel.validation.importIssues.jsonValidationCode import JsonValidationCode
from app.dataModel.validation.importIssues.wireShapeIssue import WireShapeIssue

_GRAVITY_ERRORS = frozenset(("float_type", "greater_than_equal", "finite_number"))


def _policy_failure(operation: PhysicsSettingsInputOperation, ctx: ResolveContext) -> PhysicsSettingsAdmissionFailure:
    return PhysicsSettingsAdmissionFailure(cause=SettingsPolicyMismatch(
        operation=operation, actual_mode=PhysicsSettingsContextMode(ctx.mode.value),
        actual_validate_only=ctx.validate_only,
    ))


def _read_full_input(raw: object, ctx: ResolveContext) -> PhysicsSettingsInputResolved | PhysicsSettingsInputRefused:
    if ctx.partial or not isinstance(raw, dict):
        return PhysicsSettingsInputRefused(issues=(WireShapeIssue(
            code=JsonValidationCode.EXPECTED_OBJECT, location=ctx.location,
            message="Physics settings input requires a full authored mapping, not a patch or captured POJO",
        ),))
    try:
        return PhysicsSettingsInputResolved(settings=WorldPhysicsSettings.model_validate(raw, strict=True))
    except ValidationError as exc:
        issues: list[PhysicsGravityTypeError | JsonFieldError | WireShapeIssue] = []
        for error in exc.errors(include_input=False):
            if error["loc"] == ("gravity_acceleration_m_s2",) and error["type"] in _GRAVITY_ERRORS:
                issues.append(PhysicsGravityTypeError(
                    code=PhysicsGravityCode.INVALID_GRAVITY, path=GRAVITY_PATH,
                    arguments=PhysicsGravityArguments.model_validate({"pydantic_type": error["type"]}),
                    location=ctx.location, message="gravity must be a finite nonnegative number in m/s²",
                ))
            elif error["type"] in ("extra_forbidden", "invalid_key"):
                mapped = field_issue(ctx, WorldPhysicsSettings, error["loc"], "unknown or invalid settings key",
                                     JsonValidationCode.REMOVED_FROM_WIRE
                                     if error["loc"] == ("g",) else JsonValidationCode.VALIDATION_ERROR)
                if not isinstance(mapped, (JsonFieldError, WireShapeIssue)):
                    raise PhysicsSettingsBoundaryFault("unexpected shared settings issue type")
                issues.append(mapped)
            else:
                raise PhysicsSettingsBoundaryFault("unmapped Physics settings input error") from exc
        return PhysicsSettingsInputRefused(issues=tuple(issues))


def validate_world_physics_settings_input(
    raw: object, *, ctx: ResolveContext,
) -> PhysicsSettingsInputResolved | PhysicsSettingsInputRefused | PhysicsSettingsAdmissionFailure:
    if not ctx.validate_only:
        return _policy_failure(PhysicsSettingsInputOperation.VALIDATE, ctx)
    result = _read_full_input(raw, ctx)
    if isinstance(result, PhysicsSettingsInputRefused):
        report_issues(ctx, result.issues)
    return result


def resolve_world_physics_settings_input_runtime(
    raw: object, *, ctx: ResolveContext,
) -> PhysicsSettingsInputResolved | PhysicsSettingsInputRefused | PhysicsSettingsAdmissionFailure:
    if ctx.mode is not ResolveMode.RUNTIME or ctx.validate_only:
        return _policy_failure(PhysicsSettingsInputOperation.RUNTIME, ctx)
    result = _read_full_input(raw, ctx)
    if isinstance(result, PhysicsSettingsInputResolved):
        return result
    # Refuse mixed/structural errors without emitting a fictitious continuation.
    if len(result.issues) != 1 or not isinstance(result.issues[0], PhysicsGravityTypeError):
        report_issues(ctx, result.issues)
        return result
    original = result.issues[0]
    cause = PhysicsGravityTypeError(
        code=original.code, path=original.path, arguments=original.arguments, location=original.location,
        message=f"invalid gravity; using default {STANDARD_GRAVITY_M_S2} m/s²",
    )
    resolved = PhysicsSettingsInputResolved(settings=WorldPhysicsSettings(), diagnostics=(
        PhysicsGravityDefaultApplied(cause=cause, selected=STANDARD_GRAVITY_M_S2),
    ))
    report_continuation(replace(ctx, schema_id=WorldPhysicsSettings.SCHEMA_ID), cause)
    return resolved
