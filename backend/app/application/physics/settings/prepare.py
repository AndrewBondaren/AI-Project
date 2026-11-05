"""Fixed pure replace/reset operations with typed refusal and admission."""

from app.application.physics.settings.capture import admit_record, build_settings_view, validate_settings_view
from app.dataModel.physics.settings.settingsCapture import WorldPhysicsSettingsView
from app.dataModel.physics.settings.settingsChange import (
    PreparedPhysicsSettingsChange, WorldPhysicsSettingsReplace, WorldPhysicsSettingsReset,
)
from app.dataModel.physics.settings.settingsIssues import (
    PhysicsSettingsAdmissionFailure, PhysicsSettingsSubject, SettingsSchemaMismatch, SettingsWorldMismatch,
)
from app.dataModel.physics.settings.settingsResults import PhysicsSettingsChangeReason, PhysicsSettingsChangeRefused
from app.dataModel.physics.settings.worldPhysicsSettings import WorldPhysicsSettings


def _check_expectation(
    request: WorldPhysicsSettingsReplace | WorldPhysicsSettingsReset, current: WorldPhysicsSettingsView,
) -> PhysicsSettingsChangeRefused | PhysicsSettingsAdmissionFailure | None:
    if request.world_uid != current.ref.world_uid:
        return PhysicsSettingsAdmissionFailure(cause=SettingsWorldMismatch(
            expected_world_uid=request.world_uid, observed_world_uid=current.ref.world_uid,
        ))
    if request.expected_ref.schema_version != current.ref.schema_version:
        return PhysicsSettingsAdmissionFailure(cause=SettingsSchemaMismatch(
            expected_version=current.ref.schema_version, observed_version=request.expected_ref.schema_version,
        ))
    if request.expected_ref != current.ref:
        return PhysicsSettingsChangeRefused(reason=PhysicsSettingsChangeReason.REVISION_MISMATCH,
                                           expected_ref=request.expected_ref, observed_ref=current.ref)
    return None


def prepare_replace_world_physics_settings(
    request: WorldPhysicsSettingsReplace, current: WorldPhysicsSettingsView,
) -> PreparedPhysicsSettingsChange | PhysicsSettingsChangeRefused | PhysicsSettingsAdmissionFailure:
    admitted_request = admit_record(request, WorldPhysicsSettingsReplace, PhysicsSettingsSubject.REPLACE)
    if isinstance(admitted_request, PhysicsSettingsAdmissionFailure):
        return admitted_request
    admitted_current = validate_settings_view(current)
    if isinstance(admitted_current, PhysicsSettingsAdmissionFailure):
        return admitted_current
    failure = _check_expectation(admitted_request, admitted_current)
    if failure is not None:
        return failure
    proposed = build_settings_view(admitted_request.world_uid, admitted_request.value)
    if isinstance(proposed, PhysicsSettingsAdmissionFailure):
        return proposed
    return PreparedPhysicsSettingsChange(world_uid=admitted_request.world_uid, expected_ref=admitted_current.ref,
                                         proposed=proposed.settings, proposed_ref=proposed.ref)


def prepare_reset_world_physics_settings(
    request: WorldPhysicsSettingsReset, current: WorldPhysicsSettingsView,
) -> PreparedPhysicsSettingsChange | PhysicsSettingsChangeRefused | PhysicsSettingsAdmissionFailure:
    admitted_request = admit_record(request, WorldPhysicsSettingsReset, PhysicsSettingsSubject.RESET)
    if isinstance(admitted_request, PhysicsSettingsAdmissionFailure):
        return admitted_request
    admitted_current = validate_settings_view(current)
    if isinstance(admitted_current, PhysicsSettingsAdmissionFailure):
        return admitted_current
    failure = _check_expectation(admitted_request, admitted_current)
    if failure is not None:
        return failure
    proposed = build_settings_view(admitted_request.world_uid, WorldPhysicsSettings())
    if isinstance(proposed, PhysicsSettingsAdmissionFailure):
        return proposed
    return PreparedPhysicsSettingsChange(world_uid=admitted_request.world_uid, expected_ref=admitted_current.ref,
                                         proposed=proposed.settings, proposed_ref=proposed.ref)
