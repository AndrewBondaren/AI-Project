"""Concrete Physics causes and explicit operation outcome narrowing."""

from typing import assert_type

from app.application.jsonValidation.resolution.diagnostics import ResolveContext
from app.application.physics.settings.input import resolve_world_physics_settings_input_runtime
from app.application.physics.settings.prepare import prepare_reset_world_physics_settings
from app.dataModel.physics.settings.settingsCapture import WorldPhysicsSettingsRef, WorldPhysicsSettingsView
from app.dataModel.physics.settings.settingsChange import PreparedPhysicsSettingsChange, WorldPhysicsSettingsReset
from app.dataModel.physics.settings.settingsInput import PhysicsSettingsInputRefused, PhysicsSettingsInputResolved
from app.dataModel.physics.settings.settingsIssues import (
    GRAVITY_PATH, PhysicsGravityArguments, PhysicsGravityCode, PhysicsGravityTypeError,
    PhysicsSettingsAdmissionCause, PhysicsSettingsAdmissionFailure,
)
from app.dataModel.physics.settings.settingsResults import PhysicsSettingsChangeRefused
from app.dataModel.validation.importIssues.wireLocation import WireLocation


def cause() -> PhysicsGravityTypeError:
    return PhysicsGravityTypeError(
        code=PhysicsGravityCode.INVALID_GRAVITY, path=GRAVITY_PATH,
        arguments=PhysicsGravityArguments(pydantic_type="float_type"), location=WireLocation(), message="invalid",
    )


def outcomes(request: WorldPhysicsSettingsReset, current: WorldPhysicsSettingsView) -> None:
    result = prepare_reset_world_physics_settings(request, current)
    if isinstance(result, PhysicsSettingsAdmissionFailure):
        assert_type(result.causes, tuple[PhysicsSettingsAdmissionCause, ...])
        return
    if isinstance(result, PhysicsSettingsChangeRefused):
        assert_type(result.expected_ref, WorldPhysicsSettingsRef)
        return
    assert_type(result, PreparedPhysicsSettingsChange)


def input_outcome(raw: object, ctx: ResolveContext) -> None:
    result = resolve_world_physics_settings_input_runtime(raw, ctx=ctx)
    if isinstance(result, (PhysicsSettingsAdmissionFailure, PhysicsSettingsInputRefused)):
        return
    assert_type(result, PhysicsSettingsInputResolved)
