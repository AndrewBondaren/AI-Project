"""Marked expressions must fail static admission."""

from app.dataModel.physics.settings.settingsInput import PhysicsSettingsInputResolved
from app.dataModel.physics.settings.settingsIssues import (
    GRAVITY_PATH, PhysicsGravityArguments, PhysicsGravityTypeError, PhysicsSettingsAdmissionFailure,
)
from app.dataModel.physics.settings.worldPhysicsSettings import WorldPhysicsSettings
from app.dataModel.validation.importIssues.jsonValidationCode import JsonValidationCode
from app.dataModel.validation.importIssues.wireLocation import WireLocation


def invalid(cause: PhysicsGravityTypeError, foreign: object) -> None:
    PhysicsGravityArguments(pydantic_type="missing")  # EXPECT: reportArgumentType
    PhysicsGravityTypeError(code=JsonValidationCode.DOMAIN_RANGE, path=GRAVITY_PATH, arguments=cause.arguments, location=WireLocation(), message="invalid")  # EXPECT: reportArgumentType
    PhysicsSettingsAdmissionFailure(cause=foreign)  # EXPECT: reportArgumentType
    PhysicsSettingsInputResolved(settings=WorldPhysicsSettings(), diagnostics=(cause,))  # EXPECT: reportArgumentType
