"""Separate fixed replace/reset operations. No I/O, persistence, or dispatch."""

from app.application.physics.settings.capture import build_settings_view, validate_settings_view
from app.dataModel.physics.settings.settingsCapture import WorldPhysicsSettingsView
from app.dataModel.physics.settings.settingsChange import (
    PreparedPhysicsSettingsChange, WorldPhysicsSettingsReplace, WorldPhysicsSettingsReset,
)
from app.dataModel.physics.settings.settingsResults import PhysicsSettingsChangeReason, PhysicsSettingsChangeRefused
from app.dataModel.physics.settings.worldPhysicsSettings import WorldPhysicsSettings
from app.dataModel.validation.immutableValue import validate_immutable


def prepare_replace_world_physics_settings(
    request: WorldPhysicsSettingsReplace, current: WorldPhysicsSettingsView,
) -> PreparedPhysicsSettingsChange | PhysicsSettingsChangeRefused:
    validate_immutable(request)
    request = WorldPhysicsSettingsReplace.model_validate(request, strict=True)
    current = validate_settings_view(current)
    if request.expected_ref != current.ref:
        return PhysicsSettingsChangeRefused(reason=PhysicsSettingsChangeReason.STALE_SETTINGS)
    proposed = build_settings_view(request.world_uid, request.value)
    return PreparedPhysicsSettingsChange(world_uid=request.world_uid, expected_ref=current.ref,
                                        proposed=proposed.settings, proposed_ref=proposed.ref)


def prepare_reset_world_physics_settings(
    request: WorldPhysicsSettingsReset, current: WorldPhysicsSettingsView,
) -> PreparedPhysicsSettingsChange | PhysicsSettingsChangeRefused:
    validate_immutable(request)
    request = WorldPhysicsSettingsReset.model_validate(request, strict=True)
    current = validate_settings_view(current)
    if request.expected_ref != current.ref:
        return PhysicsSettingsChangeRefused(reason=PhysicsSettingsChangeReason.STALE_SETTINGS)
    proposed = build_settings_view(request.world_uid, WorldPhysicsSettings())
    return PreparedPhysicsSettingsChange(world_uid=request.world_uid, expected_ref=current.ref,
                                        proposed=proposed.settings, proposed_ref=proposed.ref)
